"""定投回测接口。"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.calc import CalcDcaBacktest
from ..models.raw import RawPriceDaily
from ..models.result import ResultDcaSummary
from ..schemas.backtest import (
    BacktestCreated,
    BacktestRequest,
    ChartData,
    SummaryData,
)
from ..schemas.common import ApiResponse
from ..services.compute.dca import ComputeError, DcaParams, lookback_days, make_task_id, run_backtest
from ..services.fetcher import FetchError, get_fetcher
from ..services.storage import upsert_bars
from ..services.symbol_catalog import lookup_name

logger = logging.getLogger(__name__)
router = APIRouter()

# 收益率基准：沪深300（用 510300 ETF 代表，收益率与指数一致）
BENCHMARK_SYMBOL = "510300"
BENCHMARK_NAME = "沪深300"

# 起点端允许的假期偏差：MIN 比 start 晚不超过此值视为已覆盖（避免春节等假期误判为缺数据）
_FRONT_TOL = timedelta(days=7)


@router.post("/dca", response_model=ApiResponse)
def create_dca_backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """创建定投回测任务。

    流程：命中同参数已算结果 → 直接返回；否则按模式回溯补数据 → 计算 → 返回 task_id。
    """
    params = DcaParams(
        symbol=req.symbol,
        frequency=req.frequency,
        amount=req.amount,
        start_date=req.start_date,
        end_date=req.end_date,
        invest_day=req.invest_day,
        mode=req.mode,
        ma_period=req.ma_period,
    )
    task_id = make_task_id(params)

    # 命中已算过的同参数回测：直接返回 task_id，跳过重复计算与重复拉取
    if db.get(ResultDcaSummary, task_id) is not None:
        return ApiResponse.ok(data=BacktestCreated(task_id=task_id))

    fetch_start = req.start_date - timedelta(days=lookback_days(req.mode, req.ma_period))
    err = _ensure_data(db, req.symbol, fetch_start, req.end_date)
    if err:
        return ApiResponse.error(message=err)

    # 基准（沪深300）行情：best-effort，失败不影响回测
    _ensure_data(db, BENCHMARK_SYMBOL, req.start_date, req.end_date)

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
    benchmark_returns, benchmark_name = _benchmark_returns(db, rows, summary)

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


def _benchmark_returns(
    db: Session, rows: list[CalcDcaBacktest], summary: ResultDcaSummary | None
) -> tuple[list[float | None], str]:
    """计算沪深300 在回测区间的累计收益率（相对区间首日），按回测交易日对齐。"""
    if not summary:
        return [], ""
    bench = {
        r.trade_date: Decimal(str(r.close))
        for r in db.execute(
            select(RawPriceDaily.trade_date, RawPriceDaily.close).where(
                RawPriceDaily.symbol == BENCHMARK_SYMBOL,
                RawPriceDaily.trade_date >= summary.start_date,
                RawPriceDaily.trade_date <= summary.end_date,
            )
        ).all()
    }
    if not bench:
        return [None] * len(rows), ""

    # 基准起点：回测首个交易日（或之后首个有数据的交易日）
    first_date = rows[0].trade_date
    base_close = bench.get(first_date)
    if base_close is None:
        for d in sorted(bench):
            if d >= first_date:
                base_close = bench[d]
                break
    if not base_close or base_close <= 0:
        return [None] * len(rows), BENCHMARK_NAME

    out: list[float | None] = []
    for r in rows:
        c = bench.get(r.trade_date)
        out.append(float((c / base_close - 1) * 100) if c else None)
    return out, BENCHMARK_NAME


def _ensure_data(db: Session, symbol: str, start: date, end: date) -> str | None:
    """确保 [start, end] 区间行情完整：已覆盖则跳过，缺前段/后段则补拉对应子区间。

    旧实现仅判 count==0，会把"部分覆盖"误判为完整；现按 MIN/MAX 判定并补缺段。
    返回错误信息或 None。
    """
    row = db.execute(
        select(
            func.min(RawPriceDaily.trade_date),
            func.max(RawPriceDaily.trade_date),
            func.count(),
        )
        .select_from(RawPriceDaily)
        .where(
            RawPriceDaily.symbol == symbol,
            RawPriceDaily.trade_date >= start,
            RawPriceDaily.trade_date <= end,
        )
    ).one()
    mn, mx, cnt = row[0], row[1], row[2]

    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    else:
        if mn > start + _FRONT_TOL:
            ranges.append((start, mn))  # 前段缺失：拉到已有最早日（含，UPSERT 幂等）
        if mx < end:
            ranges.append((mx, end))  # 后段缺失 / 有新数据：从已有最晚日（含）拉到 end

    if not ranges:
        return None  # 区间已覆盖，无需拉取

    for s, e in ranges:
        try:
            bars = get_fetcher().fetch_daily(symbol, s, e)
        except FetchError as ex:
            return f"数据缺失且自动拉取失败（{symbol} {s}~{e}）：{ex}"
        except Exception as ex:  # noqa: BLE001
            return f"数据缺失且自动拉取失败（{symbol} {s}~{e}）：{ex}"

        if bars:
            upsert_bars(db, bars)
        else:
            logger.info("%s 在 %s~%s 无可拉取行情（可能为未来日期或已退市）", symbol, s, e)
    return None
