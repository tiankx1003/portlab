"""网格交易策略回测（020）持久化模型。

镜像 drawboard（calc/result 两表）：
- ``CalcGridBacktest``：逐日明细（含冗余 close 与 grid_index，GET /chart 直读）。
- ``ResultGridSummary``：汇总指标（含特色字段 grid_profit 网格套利差价 / cycle_count 完成循环）。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CalcGridBacktest(Base):
    """网格交易策略回测逐日计算结果。"""

    __tablename__ = "calc_grid_backtest"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    signal: Mapped[str] = mapped_column(String(8), nullable=False, default="hold")  # buy/sell/hold
    action_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    holding_shares: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    cum_invested: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    cum_proceeds: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    return_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    close: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)  # 冗余收盘
    grid_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 所在格(可负)


class ResultGridSummary(Base):
    """网格交易策略回测汇总指标。"""

    __tablename__ = "result_grid_summary"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    center_price: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    step_pct: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)  # 网格间距 %
    amount_per_level: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    n_levels_above: Mapped[int] = mapped_column(Integer, nullable=False)
    n_levels_below: Mapped[int] = mapped_column(Integer, nullable=False)
    bound_mode: Mapped[str] = mapped_column(String(8), nullable=False)  # hold/stop/reset
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_invested: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    final_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_return_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    annualized_return: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)  # XIRR
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    buy_count: Mapped[int] = mapped_column(Integer, nullable=False)
    sell_count: Mapped[int] = mapped_column(Integer, nullable=False)
    grid_profit: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)  # 网格套利累计差价
    cycle_count: Mapped[int] = mapped_column(Integer, nullable=False)  # 完成的买卖循环次数
