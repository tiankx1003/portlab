"""估值看板 v2 schema（024）。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Lookback = Literal["1y", "3y", "5y", "7y", "10y", "all"]


class IndexItem(BaseModel):
    """下拉项（含 supported / note）。"""

    index_code: str
    name_cn: str
    lg_name: str | None = None
    source_type: str
    supported: bool
    note: str | None = None
    sort_order: int = 0


class IndicesData(BaseModel):
    items: list[IndexItem]


class ValuationQuery(BaseModel):
    """单指数查询参数。"""

    symbol: str = Field(..., min_length=1, max_length=16)
    lookback: Lookback = "5y"
    start_date: date | None = None
    end_date: date | None = None


class PeChannel(BaseModel):
    l1_min: float
    l2_low: float
    l3_median: float
    l4_high: float
    l5_max: float


class SingleValuationData(BaseModel):
    available: bool
    index_code: str
    name_cn: str
    source_type: str
    supported: bool
    note: str | None = None
    dates: list[str] = []
    pe_ttm: list[float | None] = []
    pb: list[float | None] = []
    channel: dict = {}
    current_pe: float | None = None
    percentile: float | None = None
    channel_position: str = "—"
    current_pb: float | None = None
    dividend_yield: float | None = None
    pb_available: bool = False
    dividend_available: bool = False
    as_of: str | None = None
    fetch_warning: str | None = None


class OverlayQuery(BaseModel):
    """多指数叠加查询参数。"""

    symbols: list[str] = Field(..., min_length=1)
    lookback: Lookback = "5y"
    base: Literal[1, 1000] = 1
    start_date: date | None = None
    end_date: date | None = None


class OverlaySeriesItem(BaseModel):
    index_code: str
    name_cn: str
    normalized: list[float | None] = []


class OverlayData(BaseModel):
    base: int = 1
    dates: list[str] = []
    series: list[OverlaySeriesItem] = []
    note: str | None = None
