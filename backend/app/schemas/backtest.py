"""定投回测相关 schema。"""

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator


class BacktestRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    frequency: str = Field(..., pattern="^(weekly|monthly)$")
    amount: Decimal = Field(..., gt=0, description="每期定投金额")
    start_date: date
    end_date: date
    invest_day: int = Field(..., description="weekly:0-6(周一~周日); monthly:1-28")

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


class SummaryData(BaseModel):
    total_invested: float
    final_value: float
    total_pnl: float
    total_return_rate: float
    annualized_return: float
    max_drawdown: float
    invest_count: int


class SymbolItem(BaseModel):
    code: str
    name: str
    type: str
