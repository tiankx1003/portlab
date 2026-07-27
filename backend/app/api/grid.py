"""网格交易策略回测接口（020）。

克隆 drawboard（POST 落库 + GET chart/summary），路由挂在 /api/backtest 下与 ma120 并列：
- POST /api/backtest/grid                  提交参数 → 命中缓存或补数据 → 计算 → 落库 → task_id。
- GET  /api/backtest/grid/{task_id}/chart  读 calc_grid_backtest 逐日（含 grid_levels 网格线）。
- GET  /api/backtest/grid/{task_id}/summary 读 result_grid_summary 汇总。
"""

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.grid import ResultGridSummary
from ..schemas.common import ApiResponse
from ..schemas.grid import (
    GridBacktestResult,
    GridChartData,
    GridCreated,
    GridPoint,
    GridRequest,
    GridSummaryData,
)
from ..services.benchmark import BENCHMARK_SYMBOL, compute_benchmark_returns
from ..services.compute.grid import (
    ComputeError,
    GridParams,
    build_grid_levels,
    load_chart_rows,
    make_task_id,
    run_backtest,
    run_realtime,
)
from ..services.fetcher.registry import resolve_source, source_from_task_id
from ..services.price_data import ensure_price_data
from ..services.symbol_catalog import lookup_name
from ..services.recent import log_save

router = APIRouter()


@router.post("/grid", response_model=ApiResponse)
def create_grid(req: GridRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """提交网格回测：命中同参数已算结果 → 直接返回；否则补数据 → 计算 → 写两表 → task_id。"""
    src = resolve_source(db)
    params = GridParams(
        symbol=req.symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        center_price=Decimal(str(req.center_price)),
        step_pct=Decimal(str(req.step_pct)),
        amount_per_level=Decimal(str(req.amount_per_level)),
        n_levels_above=req.n_levels_above,
        n_levels_below=req.n_levels_below,
        bound_mode=req.bound_mode,
        source=src,
    )
    task_id = make_task_id(params)

    # 幂等命中：同参数已算过则直接返回 task_id，跳过重复计算与重复拉取
    if db.get(ResultGridSummary, task_id) is not None:
        log_save(db, task_id, "grid", req.symbol)
        return ApiResponse.ok(data=GridCreated(task_id=task_id))

    # 未命中：补数据 → 计算 → 落库
    err = ensure_price_data(db, req.symbol, req.start_date, req.end_date)
    if err:
        return ApiResponse.error(message=err)
    ensure_price_data(db, BENCHMARK_SYMBOL, req.start_date, req.end_date)  # 基准 best-effort

    try:
        run_backtest(db, params)
    except ComputeError as e:
        return ApiResponse.error(message=str(e))

    log_save(db, task_id, "grid", req.symbol)
    return ApiResponse.ok(data=GridCreated(task_id=task_id))


@router.post("/grid/preview", response_model=ApiResponse)
def preview_grid(req: GridRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """实时预览回测（不落库）：返回 chart + summary，供「开始回测」按钮快速响应。"""
    src = resolve_source(db)
    params = GridParams(
        symbol=req.symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        center_price=Decimal(str(req.center_price)),
        step_pct=Decimal(str(req.step_pct)),
        amount_per_level=Decimal(str(req.amount_per_level)),
        n_levels_above=req.n_levels_above,
        n_levels_below=req.n_levels_below,
        bound_mode=req.bound_mode,
        source=src,
    )
    err = ensure_price_data(db, req.symbol, req.start_date, req.end_date)
    if err:
        return ApiResponse.error(message=err)
    ensure_price_data(db, BENCHMARK_SYMBOL, req.start_date, req.end_date)  # best-effort
    try:
        raw = run_realtime(db, params)
    except ComputeError as e:
        return ApiResponse.error(message=str(e))
    return ApiResponse.ok(data=GridBacktestResult(**raw))


@router.get("/grid/{task_id}/chart", response_model=ApiResponse)
def get_grid_chart(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    rows = load_chart_rows(db, task_id)
    if not rows:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}（可能尚未保存或参数有误）")

    summary = db.get(ResultGridSummary, task_id)
    trade_dates = [r.trade_date for r in rows]
    if summary:
        benchmark_returns, benchmark_name = compute_benchmark_returns(
            db,
            trade_dates,
            summary.start_date,
            summary.end_date,
            source=source_from_task_id(task_id),
        )
        symbol_name = lookup_name(summary.symbol)
        grid_levels = [
            float(x)
            for x in build_grid_levels(
                summary.center_price,
                summary.step_pct,
                summary.n_levels_above,
                summary.n_levels_below,
            )
        ]
    else:
        benchmark_returns, benchmark_name, symbol_name, grid_levels = [], "", "", []

    buy_points: list[GridPoint] = []
    sell_points: list[GridPoint] = []
    for r in rows:
        if r.signal == "buy":
            buy_points.append(
                GridPoint(date=r.trade_date, price=float(r.close), amount=float(r.action_amount))
            )
        elif r.signal == "sell":
            sell_points.append(
                GridPoint(date=r.trade_date, price=float(r.close), amount=float(r.action_amount))
            )

    data = GridChartData(
        dates=trade_dates,
        close_prices=[float(r.close) for r in rows],
        market_values=[float(r.market_value) for r in rows],
        total_cost=[float(r.cum_invested) for r in rows],
        pnl=[float(r.pnl) for r in rows],
        return_rates=[float(r.return_rate) for r in rows],
        holding=[float(r.holding_shares) for r in rows],
        signals=[r.signal for r in rows],
        grid_levels=grid_levels,
        buy_points=buy_points,
        sell_points=sell_points,
        grid_index=[r.grid_index for r in rows],
        benchmark_returns=benchmark_returns,
        benchmark_name=benchmark_name,
        symbol_name=symbol_name,
    )
    return ApiResponse.ok(data=data)


@router.get("/grid/{task_id}/summary", response_model=ApiResponse)
def get_grid_summary(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    s = db.get(ResultGridSummary, task_id)
    if s is None:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}")

    data = GridSummaryData(
        total_invested=float(s.total_invested),
        final_value=float(s.final_value),
        total_pnl=float(s.total_pnl),
        total_return_rate=float(s.total_return_rate),
        annualized_return=float(s.annualized_return),
        max_drawdown=float(s.max_drawdown),
        buy_count=s.buy_count,
        sell_count=s.sell_count,
        grid_profit=float(s.grid_profit),
        cycle_count=s.cycle_count,
        center_price=float(s.center_price),
        step_pct=float(s.step_pct),
        amount_per_level=float(s.amount_per_level),
        n_levels_above=s.n_levels_above,
        n_levels_below=s.n_levels_below,
        bound_mode=s.bound_mode,
    )
    return ApiResponse.ok(data=data)
