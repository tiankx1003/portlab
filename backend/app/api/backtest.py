"""定投回测接口。"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.calc import CalcDcaBacktest
from ..models.result import ResultDcaSummary
from ..schemas.backtest import (
    BacktestCreated,
    BacktestRequest,
    ChartData,
    SummaryData,
)
from ..schemas.common import ApiResponse
from ..services.benchmark import BENCHMARK_SYMBOL, compute_benchmark_returns
from ..services.compute.dca import (
    ComputeError,
    DcaParams,
    lookback_days,
    make_task_id,
    run_backtest,
)
from ..services.fetcher.registry import resolve_source, source_from_task_id
from ..services.price_data import ensure_price_data
from ..services.symbol_catalog import lookup_name

router = APIRouter()


@router.post("/dca", response_model=ApiResponse)
def create_dca_backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """创建定投回测任务。

    流程：命中同参数已算结果 → 直接返回；否则按模式回溯补数据 → 计算 → 返回 task_id。
    数据源由开关决定（开启 Tushare 则用 Tushare 表 + task_id 追加 _tushare）。
    """
    src = resolve_source(db)
    params = DcaParams(
        symbol=req.symbol,
        frequency=req.frequency,
        amount=req.amount,
        start_date=req.start_date,
        end_date=req.end_date,
        invest_day=req.invest_day,
        mode=req.mode,
        ma_period=req.ma_period,
        source=src,
    )
    task_id = make_task_id(params)

    # 命中已算过的同参数回测：直接返回 task_id，跳过重复计算与重复拉取
    if db.get(ResultDcaSummary, task_id) is not None:
        return ApiResponse.ok(data=BacktestCreated(task_id=task_id))

    fetch_start = req.start_date - timedelta(days=lookback_days(req.mode, req.ma_period))
    err = ensure_price_data(db, req.symbol, fetch_start, req.end_date)
    if err:
        return ApiResponse.error(message=err)

    # 基准（沪深300）行情：best-effort，失败不影响回测
    ensure_price_data(db, BENCHMARK_SYMBOL, req.start_date, req.end_date)

    try:
        run_backtest(db, params)
    except ComputeError as e:
        return ApiResponse.error(message=str(e))

    return ApiResponse.ok(data=BacktestCreated(task_id=task_id))


@router.get("/dca/{task_id}/chart", response_model=ApiResponse)
def get_chart(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    rows = (
        db.execute(
            select(CalcDcaBacktest)
            .where(CalcDcaBacktest.task_id == task_id)
            .order_by(CalcDcaBacktest.trade_date)
        )
        .scalars()
        .all()
    )
    if not rows:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}（可能尚未计算或参数有误）")

    summary = db.get(ResultDcaSummary, task_id)
    symbol_name = lookup_name(summary.symbol) if summary else ""
    if summary:
        benchmark_returns, benchmark_name = compute_benchmark_returns(
            db,
            [r.trade_date for r in rows],
            summary.start_date,
            summary.end_date,
            source=source_from_task_id(task_id),
        )
    else:
        benchmark_returns, benchmark_name = [], ""

    data = ChartData(
        dates=[r.trade_date for r in rows],
        market_value=[float(r.market_value) for r in rows],
        total_cost=[float(r.cum_cost) for r in rows],
        pnl=[float(r.pnl) for r in rows],
        return_rate=[float(r.return_rate) for r in rows],
        invest_days=[bool(r.is_invest_day) for r in rows],
        deduction_rates=[
            float(r.deduction_rate) if (r.is_invest_day and r.deduction_rate is not None) else None
            for r in rows
        ],
        actual_amounts=[
            float(r.actual_amount) if (r.is_invest_day and r.actual_amount is not None) else None
            for r in rows
        ],
        benchmark_returns=benchmark_returns,
        benchmark_name=benchmark_name,
        symbol_name=symbol_name,
    )
    return ApiResponse.ok(data=data)


@router.get("/dca/{task_id}/summary", response_model=ApiResponse)
def get_summary(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    s = db.get(ResultDcaSummary, task_id)
    if s is None:
        return ApiResponse.error(message=f"未找到回测任务 {task_id}")

    data = SummaryData(
        total_invested=float(s.total_invested),
        final_value=float(s.final_value),
        total_pnl=float(s.total_pnl),
        total_return_rate=float(s.total_return_rate),
        annualized_return=float(s.annualized_return),
        max_drawdown=float(s.max_drawdown),
        invest_count=s.invest_count,
        symbol_name=lookup_name(s.symbol),
    )
    return ApiResponse.ok(data=data)

