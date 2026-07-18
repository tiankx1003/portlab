"""市场概览 schema。"""

from datetime import date

from pydantic import BaseModel


class MarketItem(BaseModel):
    symbol: str
    name: str
    latest_date: date
    latest_close: float
    prev_close: float | None
    change_pct: float | None  # 当日涨跌幅(%)
    sparkline: list[float]  # 最近 30 个交易日收盘（升序）


class MarketOverview(BaseModel):
    as_of: date | None  # 所有 items 中最新日期；无数据则 None
    items: list[MarketItem]
    missing: list[str]  # 库里完全无数据的 symbol
