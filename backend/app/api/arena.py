"""策略擂台接口（023）。

GET /api/arena/compare —— 跨策略（固定 symbol 列所有策略）/ 跨标的（固定策略列多标的）对比。
无 task_id、无持久化，即查即返回对比视图。
"""

from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.arena import ArenaData, NavSeries, StrategyResultItem
from ..schemas.common import ApiResponse
from ..services.arena import get_normalized_nav, list_strategy_results

router = APIRouter()


@router.get("/compare", response_model=ApiResponse)
def compare(
    mode: Literal["cross_strategy", "cross_symbol"],
    symbol: str | None = None,
    strategy: str | None = None,
    symbols: list[str] = Query(default_factory=list),
    start: date | None = None,
    end: date | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """横向对比：返回对比项 + 各 task_id 归一化净值（起点=100）。"""
    if mode == "cross_strategy" and not symbol:
        return ApiResponse.error(message="cross_strategy 模式需指定 symbol")
    if mode == "cross_symbol" and not strategy:
        return ApiResponse.error(message="cross_symbol 模式需指定 strategy")

    rows = list_strategy_results(db, mode, symbol, strategy, symbols or None, start, end)
    items = [StrategyResultItem(**r) for r in rows]
    nav_series: dict[str, NavSeries] = {}
    for it in items:
        dates, nav = get_normalized_nav(db, it.task_id, it.strategy)
        if dates:
            nav_series[it.task_id] = NavSeries(dates=dates, nav=nav)

    return ApiResponse.ok(data=ArenaData(items=items, nav_series=nav_series))
