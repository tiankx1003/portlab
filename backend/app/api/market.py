"""市场概览接口（首页用）。仅读 raw_price_daily，不主动拉取。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.common import ApiResponse
from ..schemas.market import MarketItem, MarketOverview
from ..services.market import get_market_overview

router = APIRouter()


@router.get("/overview", response_model=ApiResponse)
def overview(extra: str | None = None, db: Session = Depends(get_db)) -> ApiResponse:
    """预置指数 + 可选自定义代码（extra）的最新价 / 涨跌幅 / sparkline；无数据的进入 missing。"""
    raw = get_market_overview(db, extra=extra)
    data = MarketOverview(
        as_of=raw["as_of"],
        items=[MarketItem(**item) for item in raw["items"]],
        missing=raw["missing"],
    )
    return ApiResponse.ok(data=data)
