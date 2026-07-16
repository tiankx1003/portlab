"""MA120 策略回测接口。与 /api/backtest/dca 并列。"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.calc import CalcMa120Backtest
from ..models.raw import RawPriceDaily
from ..models.result import ResultMa120Summary
from ..schemas.common import ApiResponse
from ..schemas.ma120 import (
    Ma120ChartData,
    Ma120Created,
    Ma120Point,
    Ma120Request,
    Ma120SummaryData,
)
from ..services.benchmark import BENCHMARK_SYMBOL, compute_benchmark_returns
from ..services.compute.ma120 import (
    ComputeError,
    Ma120Params,
    lookback_days,
    make_task_id,
    run_backtest,
)
from ..services.price_data import ensure_price_data
from ..services.symbol_catalog import lookup_name

router = APIRouter()


@router.post("/ma120", response_model=ApiResponse)
def create_ma120_backtest(req: Ma120Request, db: Session = Depends(get_db)) -> ApiResponse:
    """创建 MA120 策略回测任务。

    流程：命中同参数已算结果 → 直接返回；否则回溯补数据 → 计算 → 返回 task_id。
    """
    # 按资金模式归一化无关字段，保证 task_id 确定（recurring 忽略 principal，fixed 忽略 monthly）
    principal = req.principal if req.capital_mode in ("fixed", "hybrid") else None
    monthly_amount = req.monthly_amount if req.capital_mode in ("recurring", "hybrid") else None

    params = Ma120Params(
        symbol=req.symbol,
        start_date=req.start_date,
        end_date=req.end_date,
        capital_mode=req.capital_mode,
        principal=principal,
        monthly_amount=monthly_amount,
        splits=req.splits,
        ma_period=req.ma_period,
        buy_threshold=req.buy_threshold,
        step=req.step,
        crash_threshold=req.crash_threshold,
        crash_multiplier=req.crash_multiplier,
        sell_mode=req.sell_mode,
        batch_sell_step=req.batch_sell_step,
        dividend_mode=req.dividend_mode,
    )
    task_id = make_task_id(params)

    # 幂等命中：同参数已算过则直接返回 task_id
    if db.get(ResultMa120Summary, task_id) is not None:
        return ApiResponse.ok(data=Ma120Created(task_id=task_id))

    fetch_start = req.start_date - timedelta(days=lookback_days(req.ma_period))
    err = ensure_price_data(db, req.symbol, fetch_start, req.end_date)
    if err:
        return ApiResponse.error(message=err)

    # 基准（沪深300）行情：best-effort，失败不影响回测
    ensure_price_data(db, BENCHMARK_SYMBOL, req.start_date, req.end_date)

    try:
        run_backtest(db, params)
    except ComputeError as e:
        return ApiResponse.error(message=str(e))

    return ApiResponse.ok(data=Ma120Created(task_id=task_id))


@router.get("/ma120/{task_id}/chart", response_model=ApiResponse)
def get_ma120_chart(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    rows = (
        db.execute(
            select(CalcMa120Backtest)
            .where(CalcMa120Backtest.task_id == task_id)
            .order_by(CalcMa120Backtest.trade_date)
        )
        .scalars()
        .all()
    )
    if not rows:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}（可能尚未计算或参数有误）")

    summary = db.get(ResultMa120Summary, task_id)
    symbol_name = lookup_name(summary.symbol) if summary else ""

    # 收盘价从 raw_price_daily 读取（calc 表未存 close），用于 markPoint 与 tooltip
    closes: dict = {}
    if summary:
        closes = {
            r.trade_date: float(r.close)
            for r in db.execute(
                select(RawPriceDaily.trade_date, RawPriceDaily.close).where(
                    RawPriceDaily.symbol == summary.symbol,
                    RawPriceDaily.trade_date >= rows[0].trade_date,
                    RawPriceDaily.trade_date <= rows[-1].trade_date,
                )
            ).all()
        }

    trade_dates = [r.trade_date for r in rows]
    if summary:
        benchmark_returns, benchmark_name = compute_benchmark_returns(
            db, trade_dates, summary.start_date, summary.end_date
        )
    else:
        benchmark_returns, benchmark_name = [], ""

    buy_points: list[Ma120Point] = []
    sell_points: list[Ma120Point] = []
    for r in rows:
        if r.signal in ("buy", "sell"):
            pt = Ma120Point(
                date=r.trade_date,
                price=closes.get(r.trade_date, 0.0),
                amount=float(r.action_amount),
            )
            (buy_points if r.signal == "buy" else sell_points).append(pt)

    data = Ma120ChartData(
        dates=trade_dates,
        market_value=[float(r.market_value) for r in rows],
        total_cost=[float(r.cum_invested) for r in rows],
        pnl=[float(r.pnl) for r in rows],
        return_rate=[float(r.return_rate) for r in rows],
        ma_values=[float(r.ma_value) if r.ma_value is not None else None for r in rows],
        close_prices=[closes.get(r.trade_date) for r in rows],
        holding_shares=[float(r.holding_shares) for r in rows],
        price_vs_ma=[float(r.price_vs_ma) if r.price_vs_ma is not None else None for r in rows],
        signals=[r.signal for r in rows],
        buy_points=buy_points,
        sell_points=sell_points,
        benchmark_returns=benchmark_returns,
        benchmark_name=benchmark_name,
        symbol_name=symbol_name,
    )
    return ApiResponse.ok(data=data)


@router.get("/ma120/{task_id}/summary", response_model=ApiResponse)
def get_ma120_summary(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    s = db.get(ResultMa120Summary, task_id)
    if s is None:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}")

    data = Ma120SummaryData(
        total_invested=float(s.total_invested),
        final_value=float(s.final_value),
        total_pnl=float(s.total_pnl),
        total_return_rate=float(s.total_return_rate),
        annualized_return=float(s.annualized_return),
        max_drawdown=float(s.max_drawdown),
        buy_count=s.buy_count,
        sell_count=s.sell_count,
        dividend_total=float(s.dividend_total),
        win_rate=float(s.win_rate),
        symbol_name=lookup_name(s.symbol),
    )
    return ApiResponse.ok(data=data)
