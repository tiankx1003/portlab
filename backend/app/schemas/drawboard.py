"""基于最大回撤买入策略看板 schema（015 → 019 v2）。

- ``DrawdownSeries``：v1 行情+回撤底图序列（GET /series，保留）。
- ``DrawboardChartData``：图表数据（实时 GET /backtest 与 DB GET /{task_id}/chart 同构，对齐 Ma120ChartData）。
- ``DrawBacktestResult``：实时 GET /backtest = 图表数据 + summary。
- ``DrawSummary``：汇总（v2 补 annualized_return / max_drawdown / sell_mode）。
- ``DrawboardRequest`` / ``DrawboardSaved``：POST /save 入参与回包。
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.symbol import strip_market_prefix


class DrawdownSeries(BaseModel):
    dates: list[date]
    prices: list[float]  # 原始收盘价
    price_pct: list[float | None]  # 起算至今累计涨幅 %
    drawdown: list[float | None]  # 滚动最大回撤 %（≤0）
    benchmark_dates: list[date]
    benchmark_pct: list[float | None]  # 510300 起算至今累计涨幅 %


class DrawPoint(BaseModel):
    date: date
    price: float
    amount: float


class DrawSummary(BaseModel):
    total_invested: float
    final_value: float
    total_pnl: float
    total_return_rate: float
    annualized_return: float
    max_drawdown: float
    buy_count: int
    sell_count: int
    sell_mode: str


class DrawboardChartData(BaseModel):
    """图表数据（实时与 DB 路径同构，对齐 Ma120ChartData 结构）。"""

    dates: list[date]
    market_values: list[float]  # 左轴：市值
    total_cost: list[float]  # 左轴：累计投入
    pnl: list[float]  # 左轴：盈亏（堆叠柱）
    return_rates: list[float]  # 右轴1：收益率 %
    close_prices: list[float]  # 右轴2：收盘价（带买卖 markPoint）
    drawdown: list[float]  # 右轴1：当日回撤 %（替代 MA120 的 MA 线）
    holding: list[float]  # 持仓份额
    signals: list[str]  # buy/sell/hold
    buy_points: list[DrawPoint]
    sell_points: list[DrawPoint]
    benchmark_returns: list[float | None] = []
    benchmark_name: str = ""
    symbol_name: str = ""


class DrawBacktestResult(DrawboardChartData):
    """实时 GET /backtest：图表数据 + 汇总。"""

    summary: DrawSummary


class DrawboardRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32)
    start_date: date
    end_date: date
    threshold: float = Field(20.0, gt=0, description="回撤买入阈值 %")
    step: float = Field(5.0, gt=0, description="每再多跌 N% 加仓")
    buy_amount: float = Field(10000.0, gt=0, description="首次买入金额")
    add_amount: float = Field(5000.0, gt=0, description="每次加仓金额")
    sell_mode: Literal["none", "new_high", "partial"] = "new_high"
    reinvest: bool = Field(False, description="复利：按净资产高水位放大买入金额（盈利再投）")

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        v = strip_market_prefix(v)
        if not v:
            raise ValueError("标的代码不能为空")
        return v

    @model_validator(mode="after")
    def _validate(self) -> "DrawboardRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date 必须早于 end_date")
        return self


class DrawboardSaved(BaseModel):
    task_id: str
