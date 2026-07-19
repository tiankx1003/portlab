"""基于最大回撤买入策略看板（015 → 019 v2）持久化模型。

镜像 MA120（calc/result 两表）：
- ``CalcDrawboardBacktest``：逐日回测明细（含冗余 close 与 drawdown，GET /chart 直读，免回查行情表）。
- ``ResultDrawboardSummary``：汇总指标（含 annualized_return / max_drawdown，v1 缺、本任务补）。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CalcDrawboardBacktest(Base):
    """回撤买入策略回测逐日计算结果。"""

    __tablename__ = "calc_drawboard_backtest"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    signal: Mapped[str] = mapped_column(String(8), nullable=False, default="hold")  # buy/sell/hold
    action_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    holding: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False, default=0)
    cum_invested: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    cum_proceeds: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, default=0)
    return_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False, default=0)
    drawdown: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False, default=0)  # 当日回撤 %
    close: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)  # 冗余收盘


class ResultDrawboardSummary(Base):
    """回撤买入策略回测汇总指标。"""

    __tablename__ = "result_drawboard_summary"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    sell_mode: Mapped[str] = mapped_column(String(8), nullable=False)  # none/new_high/partial
    threshold: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    step: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    buy_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    add_amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
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
