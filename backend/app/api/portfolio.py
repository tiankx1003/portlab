"""组合回测接口（022）。

克隆 drawboard（POST 落库 + GET chart/summary），路由挂在 /api/backtest 下：
- POST /api/backtest/portfolio  多标的 → ensure → 计算（fixed/frontier）→ 落库 → task_id。
- GET  /api/backtest/portfolio/{task_id}/chart  净值+基准+相关性（frontier 额外前沿）。
- GET  /api/backtest/portfolio/{task_id}/summary 汇总指标。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.portfolio import ResultPortfolioSummary
from ..schemas.common import ApiResponse
from ..schemas.portfolio import (
    FrontierData,
    FrontierPoint,
    PortfolioChartData,
    PortfolioCreated,
    PortfolioRequest,
    PortfolioSummaryData,
    SingleAssetPoint,
)
from ..services.benchmark import BENCHMARK_SYMBOL, compute_benchmark_returns
from ..services.compute.portfolio import (
    ComputeError,
    PortfolioParams,
    annualized_moments,
    correlation_matrix,
    efficient_frontier,
    load_aligned_closes,
    load_nav_rows,
    make_task_id,
    max_sharpe_weights,
    min_variance_weights,
    portfolio_stats,
    run_backtest,
)
from ..services.fetcher.registry import resolve_source, source_from_task_id
from ..services.price_data import ensure_price_data
from ..services.symbol_catalog import lookup_name

router = APIRouter()


@router.post("/portfolio", response_model=ApiResponse)
def create_portfolio(req: PortfolioRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """提交组合回测：命中同参数已算结果 → 直接返回；否则补数据 → 计算 → 写两表 → task_id。"""
    src = resolve_source(db)
    params = PortfolioParams(
        symbols=tuple(req.symbols),
        start_date=req.start_date,
        end_date=req.end_date,
        mode=req.mode,
        weights=tuple(req.weights),
        rebalance=req.rebalance,
        rf=req.rf,
        allow_short=req.allow_short,
        source=src,
    )
    task_id = make_task_id(params)

    if db.get(ResultPortfolioSummary, task_id) is not None:
        return ApiResponse.ok(data=PortfolioCreated(task_id=task_id))

    # 多标的批量补行情
    for sym in req.symbols:
        err = ensure_price_data(db, sym, req.start_date, req.end_date)
        if err:
            return ApiResponse.error(message=f"{sym}: {err}")
    ensure_price_data(db, BENCHMARK_SYMBOL, req.start_date, req.end_date)  # 基准 best-effort

    try:
        run_backtest(db, params)
    except ComputeError as e:
        return ApiResponse.error(message=str(e))

    return ApiResponse.ok(data=PortfolioCreated(task_id=task_id))


def _point(weights, mean, cov, rf) -> FrontierPoint:
    st = portfolio_stats(weights, mean, cov, rf)
    return FrontierPoint(
        weights=[float(x) for x in weights],
        ret=st["return"] * 100,
        volatility=st["volatility"] * 100,
        sharpe=st["sharpe"],
    )


@router.get("/portfolio/{task_id}/chart", response_model=ApiResponse)
def get_portfolio_chart(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    s = db.get(ResultPortfolioSummary, task_id)
    if s is None:
        return ApiResponse.error(message=f"未找到组合回测任务 {task_id}")

    symbols = s.symbols.split(",")
    rows = load_nav_rows(db, task_id)
    if not rows:
        return ApiResponse.error(message=f"未找到回测数据 {task_id}")

    dates = [r.trade_date for r in rows]
    nav = [float(r.nav) for r in rows]
    drawdown = [float(r.drawdown) for r in rows]

    src = source_from_task_id(task_id)
    _, closes = load_aligned_closes(db, symbols, s.start_date, s.end_date, src)
    corr = correlation_matrix(closes, symbols).tolist()
    symbols_name = [lookup_name(x) for x in symbols]

    bench_pct, bench_name = compute_benchmark_returns(
        db, dates, s.start_date, s.end_date, source=src
    )
    bench_nav = [(1 + p / 100) if p is not None else None for p in bench_pct]

    frontier: FrontierData | None = None
    if s.mode == "frontier":
        mean, cov = annualized_moments(closes, symbols)
        rf = float(s.rf)
        short = bool(s.allow_short)
        fr = efficient_frontier(mean, cov, rf, allow_short=short)
        single_assets: list[SingleAssetPoint] = []
        for i, sym in enumerate(symbols):
            w = [0.0] * len(symbols)
            w[i] = 1.0
            st = portfolio_stats(w, mean, cov, rf)
            single_assets.append(
                SingleAssetPoint(
                    symbol=sym,
                    name=lookup_name(sym),
                    ret=st["return"] * 100,
                    volatility=st["volatility"] * 100,
                    sharpe=st["sharpe"],
                )
            )
        ms = max_sharpe_weights(mean, cov, rf, short)
        mv = min_variance_weights(mean, cov, short)
        frontier = FrontierData(
            volatilities=[p["volatility"] * 100 for p in fr],
            returns=[p["return"] * 100 for p in fr],
            sharpes=[p["sharpe"] for p in fr],
            weights_matrix=[p["weights"] for p in fr],
            single_assets=single_assets,
            min_variance=_point(mv, mean, cov, rf),
            max_sharpe=_point(ms, mean, cov, rf),
            opt_weights=[float(x) for x in ms],
        )

    data = PortfolioChartData(
        dates=dates,
        nav=nav,
        drawdown=drawdown,
        benchmark_nav=bench_nav,
        benchmark_name=bench_name,
        correlation_symbols=symbols,
        correlation_matrix=corr,
        mode=s.mode,
        symbols_name=symbols_name,
        frontier=frontier,
    )
    return ApiResponse.ok(data=data)


@router.get("/portfolio/{task_id}/summary", response_model=ApiResponse)
def get_portfolio_summary(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    s = db.get(ResultPortfolioSummary, task_id)
    if s is None:
        return ApiResponse.error(message=f"未找到组合回测任务 {task_id}")

    data = PortfolioSummaryData(
        symbols=s.symbols.split(","),
        mode=s.mode,
        weights=[float(x) for x in s.weights.split(",")],
        rebalance=s.rebalance,
        annual_return=float(s.annual_return),
        annual_volatility=float(s.annual_volatility),
        sharpe=float(s.sharpe),
        max_drawdown=float(s.max_drawdown),
        total_return=float(s.total_return),
        rf=float(s.rf),
        allow_short=bool(s.allow_short),
    )
    return ApiResponse.ok(data=data)
