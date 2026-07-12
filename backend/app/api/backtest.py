"""定投回测接口。"""

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
from ..services.compute.dca import ComputeError, DcaParams, run_backtest
from ..services.fetcher import FetchError, get_fetcher
from ..services.storage import upsert_bars

router = APIRouter()


@router.post("/dca", response_model=ApiResponse)
def create_dca_backtest(req: BacktestRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """创建定投回测任务：自动补数据 → 计算 → 返回 task_id。"""
    err = _ensure_data(db, req.symbol, req.start_date, req.end_date)
    if err:
        return ApiResponse.error(message=err)

    try:
        task_id = run_backtest(
            db,
            DcaParams(
                symbol=req.symbol,
                frequency=req.frequency,
                amount=req.amount,
                start_date=req.start_date,
                end_date=req.end_date,
                invest_day=req.invest_day,
            ),
        )
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

    data = ChartData(
        dates=[r.trade_date for r in rows],
        market_value=[float(r.market_value) for r in rows],
        total_cost=[float(r.cum_cost) for r in rows],
        pnl=[float(r.pnl) for r in rows],
        return_rate=[float(r.return_rate) for r in rows],
        invest_days=[bool(r.is_invest_day) for r in rows],
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
    )
    return ApiResponse.ok(data=data)


def _ensure_data(db: Session, symbol: str, start, end) -> str | None:
    """区间内无行情数据时自动拉取；返回错误信息或 None。"""
    cnt = db.execute(
        select(func.count())
        .select_from(RawPriceDaily)
        .where(
            RawPriceDaily.symbol == symbol,
            RawPriceDaily.trade_date >= start,
            RawPriceDaily.trade_date <= end,
        )
    ).scalar_one()

    if cnt > 0:
        return None

    try:
        bars = get_fetcher().fetch_daily(symbol, start, end)
    except FetchError as e:
        return f"数据缺失且自动拉取失败：{e}"
    except Exception as e:  # noqa: BLE001
        return f"数据缺失且自动拉取失败：{e}"

    if not bars:
        return f"{symbol} 在 {start}~{end} 无可用行情数据，请确认标的代码与日期"

    upsert_bars(db, bars)
    return None
