"""基于最大回撤买入策略看板 schema（015）。"""

from datetime import date

from pydantic import BaseModel


class DrawdownSeries(BaseModel):
    dates: list[date]
    prices: list[float]  # 原始收盘价
    price_pct: list[float | None]  # 起算至今累计涨幅 %（左轴 0 线之上）
    drawdown: list[float | None]  # 滚动最大回撤 %（≤0，左轴 0 线之下，镜像）
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
    buy_count: int
    sell_count: int


class DrawBacktestResult(BaseModel):
    dates: list[date]
    market_values: list[float]  # 右轴：市值
    return_rates: list[float]  # 右轴：收益率 %
    buy_points: list[DrawPoint]
    sell_points: list[DrawPoint]
    summary: DrawSummary
