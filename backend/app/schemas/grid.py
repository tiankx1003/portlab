"""网格交易策略回测（020）schema。

克隆 drawboard 四件套：Request / Created / ChartData / Summary。
ChartData 多 ``grid_levels``（网格线价格数组，前端画 markLine 用）。
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.symbol import strip_market_prefix


class GridPoint(BaseModel):
    date: date
    price: float
    amount: float


class GridSummaryData(BaseModel):
    total_invested: float
    final_value: float
    total_pnl: float
    total_return_rate: float
    annualized_return: float
    max_drawdown: float
    buy_count: int
    sell_count: int
    grid_profit: float  # 网格套利累计差价（特色）
    cycle_count: int  # 完成的买卖循环次数
    center_price: float
    step_pct: float
    amount_per_level: float
    n_levels_above: int
    n_levels_below: int
    bound_mode: str


class GridChartData(BaseModel):
    dates: list[date]
    close_prices: list[float]  # 收盘价（带网格 markLine + 买卖 markPoint）
    market_values: list[float]  # 左轴：市值
    total_cost: list[float]  # 左轴：累计投入
    pnl: list[float]  # 左轴：盈亏（堆叠柱）
    return_rates: list[float]  # 右轴1：收益率 %
    holding: list[float]  # 持仓份额
    signals: list[str]  # buy/sell/hold
    grid_levels: list[float]  # 网格水平线价格（前端 markLine）
    buy_points: list[GridPoint]
    sell_points: list[GridPoint]
    grid_index: list[int]  # 当日所在格（tooltip）
    benchmark_returns: list[float | None] = []
    benchmark_name: str = ""
    symbol_name: str = ""


class GridRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    start_date: date
    end_date: date
    center_price: float = Field(..., gt=0, description="网格中枢价（元）")
    step_pct: float = Field(3.0, gt=0, description="网格间距 %（如 3）")
    amount_per_level: float = Field(5000.0, gt=0, description="每格资金 M（元）")
    n_levels_above: int = Field(5, ge=1, le=20, description="上方格数")
    n_levels_below: int = Field(5, ge=1, le=20, description="下方格数")
    bound_mode: Literal["hold", "stop", "reset"] = "hold"

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        v = strip_market_prefix(v)
        if not v:
            raise ValueError("标的代码不能为空")
        return v

    @model_validator(mode="after")
    def _validate(self) -> "GridRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date 必须早于 end_date")
        return self


class GridCreated(BaseModel):
    task_id: str
