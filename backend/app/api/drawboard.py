"""基于最大回撤买入策略看板接口（015）。

- GET /api/drawboard/series   价格 + 回撤 + 基准（左轴 0 线镜像画布）。
- GET /api/drawboard/backtest 按回撤阈值跑金字塔策略（拖动阈值线松手后调用）。
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.common import ApiResponse
from ..schemas.drawboard import (
    DrawBacktestResult,
    DrawdownSeries,
    DrawPoint,
    DrawSummary,
)
from ..services.drawboard import get_drawdown_series, run_drawdown_backtest

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
    threshold: float = 10.0,  # 回撤买入阈值 %
    step: float = 2.0,  # 每再多跌 N% 加仓
    buy_amount: float = 10000.0,  # 首次买入金额
    add_amount: float = 10000.0,  # 每次加仓金额
    db: Session = Depends(get_db),
) -> ApiResponse:
    raw = run_drawdown_backtest(db, symbol, start, end, threshold, step, buy_amount, add_amount)
    s = raw["summary"]
    data = DrawBacktestResult(
        dates=raw["dates"],
        market_values=raw["market_values"],
        return_rates=raw["return_rates"],
        buy_points=[DrawPoint(**p) for p in raw["buy_points"]],
        sell_points=[DrawPoint(**p) for p in raw["sell_points"]],
        summary=DrawSummary(**s),
    )
    return ApiResponse.ok(data=data)
