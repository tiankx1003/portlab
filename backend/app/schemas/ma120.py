"""MA120 策略回测相关 schema。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.symbol import strip_market_prefix


class Ma120Request(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    start_date: date
    end_date: date
    capital_mode: str = Field(..., pattern="^(fixed|recurring|hybrid)$")
    principal: Decimal | None = Field(None, description="初始本金（fixed/hybrid 必填）")
    monthly_amount: Decimal | None = Field(None, description="月度投入（recurring/hybrid 必填）")
    splits: int = Field(10, ge=1, le=1000, description="初始本金份数")
    ma_period: int = Field(120, ge=2, le=1000, description="均线周期")
    buy_threshold: Decimal = Field(Decimal("0.985"), gt=0, lt=2, description="起始买入阈值")
    step: Decimal = Field(Decimal("0.01"), gt=0, lt=1, description="加仓步长")
    crash_threshold: Decimal = Field(Decimal("0.05"), gt=0, lt=1, description="暴跌阈值")
    crash_multiplier: int = Field(2, ge=1, le=10, description="暴跌加倍倍数")
    sell_mode: str = Field("batch", pattern="^(batch|all|half)$")
    batch_sell_step: Decimal = Field(Decimal("0.02"), gt=0, lt=1, description="止盈步长")
    dividend_mode: str = Field("cash", pattern="^(cash|reinvest)$")

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        v = strip_market_prefix(v)
        if not v:
            raise ValueError("标的代码不能为空")
        return v

    @model_validator(mode="after")
    def _validate(self) -> "Ma120Request":
        if self.start_date >= self.end_date:
            raise ValueError("start_date 必须早于 end_date")
        if self.capital_mode == "fixed" and not (self.principal and self.principal > 0):
            raise ValueError("fixed 模式下 principal 必填且 > 0")
        if self.capital_mode == "recurring" and not (
            self.monthly_amount and self.monthly_amount > 0
        ):
            raise ValueError("recurring 模式下 monthly_amount 必填且 > 0")
        if self.capital_mode == "hybrid":
            if not (self.principal and self.principal > 0):
                raise ValueError("hybrid 模式下 principal 必填且 > 0")
            if not (self.monthly_amount and self.monthly_amount > 0):
                raise ValueError("hybrid 模式下 monthly_amount 必填且 > 0")
        return self


class Ma120Created(BaseModel):
    task_id: str


class Ma120Point(BaseModel):
    date: date
    price: float
    amount: float


class Ma120ChartData(BaseModel):
    dates: list[date]
    market_value: list[float]
    total_cost: list[float]
    pnl: list[float]
    return_rate: list[float]
    ma_values: list[float | None]
    close_prices: list[float | None]
    holding_shares: list[float]
    price_vs_ma: list[float | None]
    signals: list[str]
    buy_points: list[Ma120Point]
    sell_points: list[Ma120Point]
    benchmark_returns: list[float | None] = []
    benchmark_name: str = ""
    symbol_name: str = ""


class Ma120SummaryData(BaseModel):
    total_invested: float
    final_value: float
    total_pnl: float
    total_return_rate: float
    annualized_return: float
    max_drawdown: float
    buy_count: int
    sell_count: int
    dividend_total: float
    win_rate: float
    symbol_name: str = ""


class Ma120BacktestResult(Ma120ChartData):
    """实时 GET 预览（POST /ma120/preview）：图表数据 + 汇总。"""

    summary: Ma120SummaryData
