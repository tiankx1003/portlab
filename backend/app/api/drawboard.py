"""基于最大回撤买入策略看板接口（015 → 019 v2）。

双轨（实时 GET + 落库 POST）：
- GET  /api/drawboard/series          v1 保留：价格 + 回撤 + 基准底图。
- GET  /api/drawboard/backtest        实时重算（加 sell_mode、纠正默认值），不落库。
- POST /api/drawboard/save            提交参数 → 命中缓存或计算 → 落库 → 返回 task_id。
- GET  /api/drawboard/{task_id}/chart 读 calc_drawboard_backtest 逐日（结构与实时 GET 一致）。
- GET  /api/drawboard/{task_id}/summary 读 result_drawboard_summary 汇总。
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.drawboard import ResultDrawboardSummary
from ..schemas.common import ApiResponse
from ..schemas.drawboard import (
    DrawBacktestResult,
    DrawSummary,
    DrawboardChartData,
    DrawboardRequest,
    DrawboardSaved,
    DrawdownSeries,
    DrawPoint,
)
from ..services.benchmark import BENCHMARK_SYMBOL, compute_benchmark_returns
from ..services.drawboard import (
    ComputeError,
    DrawboardParams,
    SELL_MODES,
    get_drawdown_series,
    load_chart_rows,
    make_task_id,
    run_backtest,
    run_drawdown_backtest,
)
from ..services.fetcher.registry import resolve_source, source_from_task_id
from ..services.price_data import ensure_price_data
from ..services.symbol_catalog import lookup_name

router = APIRouter()


@router.get("/series", response_model=ApiResponse)
def series(symbol: str, start: date, end: date, db: Session = Depends(get_db)) -> ApiResponse:
    raw = get_drawdown_series(db, symbol, start, end)
    data = DrawdownSeries(**raw)
    return ApiResponse.ok(data=data)


@router.get("/backtest", response_model=ApiResponse)
def backtest(
    symbol: str,
    start: date,
    end: date,
    threshold: float = 20.0,  # 回撤买入阈值 %（v2 纠正，v1 为 10）
    step: float = 5.0,  # 每再多跌 N% 加仓（v2 纠正，v1 为 2）
    buy_amount: float = 10000.0,  # 首次买入金额
    add_amount: float = 5000.0,  # 每次加仓金额（v2 纠正，v1 为 10000）
    sell_mode: str = "new_high",  # none/new_high/partial（v2 新增，默认保留 v1 行为）
    reinvest: bool = False,  # 复利：盈利再投（按净资产高水位放大买入金额）
    db: Session = Depends(get_db),
) -> ApiResponse:
    """实时重算（不落库）：加 sell_mode、纠正默认值，供「开始回测」按钮快速响应。"""
    if sell_mode not in SELL_MODES:
        return ApiResponse.error(message=f"不支持的卖出方式: {sell_mode}（可选 none/new_high/partial）")
    raw = run_drawdown_backtest(
        db, symbol, start, end, threshold, step, buy_amount, add_amount, sell_mode, reinvest
    )
    data = DrawBacktestResult(**raw)
    return ApiResponse.ok(data=data)


@router.post("/save", response_model=ApiResponse)
def save(req: DrawboardRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """保存落库：命中同参数已算结果 → 直接返回；否则补数据 → 计算 → 写两表 → 返回 task_id。"""
    src = resolve_source(db)
    params = DrawboardParams(
        symbol=req.symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        threshold=req.threshold,
        step=req.step,
        buy_amount=req.buy_amount,
        add_amount=req.add_amount,
        sell_mode=req.sell_mode,
        reinvest=req.reinvest,
        source=src,
    )
    task_id = make_task_id(params)

    # 幂等命中：同参数已算过则直接返回 task_id
    if db.get(ResultDrawboardSummary, task_id) is not None:
        return ApiResponse.ok(data=DrawboardSaved(task_id=task_id))

    err = ensure_price_data(db, req.symbol, req.start_date, req.end_date)
    if err:
        return ApiResponse.error(message=err)
    # 基准（沪深300）行情：best-effort，失败不影响回测
    ensure_price_data(db, BENCHMARK_SYMBOL, req.start_date, req.end_date)

    try:
        run_backtest(db, params)
    except ComputeError as e:
        return ApiResponse.error(message=str(e))

    return ApiResponse.ok(data=DrawboardSaved(task_id=task_id))


@router.get("/{task_id}/chart", response_model=ApiResponse)
def get_chart(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    rows = load_chart_rows(db, task_id)
    if not rows:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}（可能尚未保存或参数有误）")

    summary = db.get(ResultDrawboardSummary, task_id)
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
    else:
        benchmark_returns, benchmark_name, symbol_name = [], "", ""

    buy_points: list[DrawPoint] = []
    sell_points: list[DrawPoint] = []
    # 成本线 = 峰值自有资金占用（资金循环口径）：从已落库的 cum_invested/cum_proceeds
    # 跑累计 max(0, cum_invested - cum_proceeds)，无需额外列。
    total_cost: list[float] = []
    peak_capital = 0.0
    for r in rows:
        if r.signal == "buy":
            buy_points.append(
                DrawPoint(date=r.trade_date, price=float(r.close), amount=float(r.action_amount))
            )
        elif r.signal == "sell":
            sell_points.append(
                DrawPoint(date=r.trade_date, price=float(r.close), amount=float(r.action_amount))
            )
        net_at_risk = float(r.cum_invested) - float(r.cum_proceeds)
        if net_at_risk > peak_capital:
            peak_capital = net_at_risk
        total_cost.append(peak_capital)

    data = DrawboardChartData(
        dates=trade_dates,
        market_values=[float(r.market_value) for r in rows],
        total_cost=total_cost,
        pnl=[float(r.pnl) for r in rows],
        return_rates=[float(r.return_rate) for r in rows],
        close_prices=[float(r.close) for r in rows],
        drawdown=[float(r.drawdown) for r in rows],
        holding=[float(r.holding) for r in rows],
        signals=[r.signal for r in rows],
        buy_points=buy_points,
        sell_points=sell_points,
        benchmark_returns=benchmark_returns,
        benchmark_name=benchmark_name,
        symbol_name=symbol_name,
    )
    return ApiResponse.ok(data=data)


@router.get("/{task_id}/summary", response_model=ApiResponse)
def get_summary(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    s = db.get(ResultDrawboardSummary, task_id)
    if s is None:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}")

    data = DrawSummary(
        total_invested=float(s.total_invested),
        final_value=float(s.final_value),
        total_pnl=float(s.total_pnl),
        total_return_rate=float(s.total_return_rate),
        annualized_return=float(s.annualized_return),
        max_drawdown=float(s.max_drawdown),
        buy_count=s.buy_count,
        sell_count=s.sell_count,
        sell_mode=s.sell_mode,
    )
    return ApiResponse.ok(data=data)
