"""策略擂台（023）schema。

- ``StrategyResultItem``：跨策略统一对比项（各策略特有字段降级为 params_summary）。
- ``ArenaData``：对比项列表 + 归一化净值序列（按 task_id 索引，供多曲线叠加）。
"""

from datetime import date

from pydantic import BaseModel


class StrategyResultItem(BaseModel):
    task_id: str
    strategy: str  # dca/ma120/drawboard/grid
    symbol: str
    symbol_name: str
    start_date: date
    end_date: date
    total_return_rate: float
    annualized_return: float
    max_drawdown: float
    sharpe: float | None = None  # 仅组合回测有，四策略暂无
    buy_count: int
    sell_count: int
    params_summary: str


class NavSeries(BaseModel):
    dates: list[date]
    nav: list[float]  # 归一化起点=100


class ArenaData(BaseModel):
    items: list[StrategyResultItem]
    nav_series: dict[str, NavSeries]  # task_id → 归一化净值
