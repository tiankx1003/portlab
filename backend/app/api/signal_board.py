"""估值与信号看板接口（032）。

- GET ``/api/signal-board/target``：第一层，单标的多维信号（技术+估值）。
- GET ``/api/signal-board/market``：第二层，大类资产估值（全收益均线+股债比价+比值+发行热度）。
- GET ``/api/signal-board/macro``：第三层，资金/宏观（Tushare，token 缺失降级）。
- GET ``/api/signal-board/resonance``：三层共振汇总（含三层明细，前端一次拿全）。
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.common import ApiResponse
from ..services.signal_board_data import (
    build_capital_macro_signals,
    build_market_signals,
    build_resonance,
    build_target_signals,
)

router = APIRouter()


@router.get("/target", response_model=ApiResponse)
def target(
    symbol: str = Query("000300", min_length=1, max_length=16),
    lookback: str = Query("5y"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """第一层：单标的信号 + PE 通道 + 股债比价。"""
    return ApiResponse.ok(data=build_target_signals(db, symbol, lookback))


@router.get("/market", response_model=ApiResponse)
def market(
    lookback: str = Query("5y"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """第二层：大类资产估值。"""
    return ApiResponse.ok(data=build_market_signals(db, lookback))


@router.get("/macro", response_model=ApiResponse)
def macro(
    lookback: str = Query("5y"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """第三层：资金/宏观（Tushare）。"""
    return ApiResponse.ok(data=build_capital_macro_signals(db, lookback))


@router.get("/resonance", response_model=ApiResponse)
def resonance(
    symbol: str = Query("000300", min_length=1, max_length=16),
    lookback: str = Query("5y"),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """三层共振汇总（含三层明细）。"""
    return ApiResponse.ok(data=build_resonance(db, symbol, lookback))
