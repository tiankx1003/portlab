"""事件冲击产业链看板 schema（018）。"""

from datetime import date

from pydantic import BaseModel, Field


# ---- 主题 / 标的池 ----
class ThemeStockItem(BaseModel):
    symbol: str
    name: str = ""
    chain_role: str  # upstream/midstream/downstream
    weight: float = 1.0


class ThemeBrief(BaseModel):
    id: int
    name: str
    is_builtin: bool
    keywords: str | None = None
    stock_count: int = 0


class ThemeDetail(BaseModel):
    id: int
    name: str
    is_builtin: bool
    keywords: str | None = None
    stocks: list[ThemeStockItem]


# ---- LLM 配置 ----
class LlmConfigUpdate(BaseModel):
    api_base: str | None = Field(default=None, max_length=255)
    api_key: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=64)
    enabled: bool | None = None


class LlmConfigStatus(BaseModel):
    enabled: bool
    api_base: str  # 非敏感，全显
    api_key_masked: str  # 如 ••••abcd，未配置为 ""
    model: str
    configured: bool  # 三项是否齐全


# ---- 智能匹配 ----
class SmartMatchRequest(BaseModel):
    event_name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)


class MatchedStock(BaseModel):
    symbol: str
    name: str = ""
    chain_role: str  # upstream/midstream/downstream
    weight: float = 1.0
    relevance: str  # high/medium/low/none


# ---- 事件 ----
class EventStockInput(BaseModel):
    symbol: str
    chain_role: str  # upstream/midstream/downstream


class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    event_date: date
    description: str | None = Field(default=None, max_length=2000)
    theme_id: int | None = None
    stocks: list[EventStockInput] | None = None  # 不传则从 theme 复制


class EventStockUpdate(BaseModel):
    stocks: list[EventStockInput]


class EventStockOut(BaseModel):
    symbol: str
    name: str = ""
    chain_role: str


class EventBrief(BaseModel):
    id: int
    name: str
    event_date: date
    description: str | None = None
    theme_id: int | None = None
    stocks: list[EventStockOut] = []


# ---- 三视图合并数据 ----
class SymbolInfo(BaseModel):
    symbol: str
    name: str
    chain_role: str


class RankingItem(BaseModel):
    symbol: str
    name: str
    change_pct: float
    chain_role: str


class WindowReturnSeries(BaseModel):
    dates: list[str]
    returns: list[float]


class ChainGroups(BaseModel):
    upstream: list[str]
    midstream: list[str]
    downstream: list[str]


class EventImpactData(BaseModel):
    event_id: int
    event_name: str
    event_date: date
    before: int
    after: int
    symbols_info: list[SymbolInfo]
    window_returns: dict[str, WindowReturnSeries]  # symbol -> series
    benchmark_symbol: str | None = None
    benchmark_name: str | None = None
    benchmark_series: WindowReturnSeries | None = None
    ranking: list[RankingItem]
    correlation_symbols: list[str]
    correlation_matrix: list[list[float]]
    chain_groups: ChainGroups
    missing: list[str] = []  # 行情缺失的标的
