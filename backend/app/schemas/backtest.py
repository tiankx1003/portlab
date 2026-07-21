"""定投回测相关 schema。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.symbol import strip_market_prefix


class BacktestRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    frequency: str = Field(..., pattern="^(weekly|monthly)$")
    amount: Decimal = Field(..., gt=0, description="每期定投金额")
    start_date: date
    end_date: date
    invest_day: int = Field(..., description="weekly:0-6(周一~周日); monthly:1-28")
    mode: str = Field("normal", pattern="^(normal|smart)$", description="普通定投/智能定投")
    ma_period: int = Field(250, ge=2, le=1000, description="智能定投均线周期")

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        v = strip_market_prefix(v)
        if not v:
            raise ValueError("标的代码不能为空")
        return v

    @model_validator(mode="after")
    def _validate(self) -> "BacktestRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date 必须早于 end_date")
        if self.frequency == "weekly" and not 0 <= self.invest_day <= 6:
            raise ValueError("weekly 时 invest_day 须为 0-6（周一到周日）")
        if self.frequency == "monthly" and not 1 <= self.invest_day <= 28:
            raise ValueError("monthly 时 invest_day 须为 1-28")
        return self


class BacktestCreated(BaseModel):
    task_id: str


class ChartData(BaseModel):
    dates: list[date]
    market_value: list[float]
    total_cost: list[float]
    pnl: list[float]
    return_rate: list[float]
    invest_days: list[bool]
    deduction_rates: list[float | None]  # 每个交易日的扣款率（非定投日为 null）
    actual_amounts: list[float | None]  # 每个交易日的实际投入（非定投日为 null）
    benchmark_returns: list[float | None] = []  # 沪深300 累计收益率参考（无数据时为 null）
    benchmark_name: str = ""  # 基准名称，如 "沪深300"
    symbol_name: str = ""


class SummaryData(BaseModel):
    total_invested: float
    final_value: float
    total_pnl: float
    total_return_rate: float
    annualized_return: float
    max_drawdown: float
    invest_count: int
    symbol_name: str = ""


class BacktestResult(ChartData):
    """实时预览（POST /dca/preview）：图表数据 + 汇总。"""

    summary: SummaryData


class SymbolItem(BaseModel):
    code: str
    name: str
    type: str
