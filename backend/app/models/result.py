"""定投回测汇总指标模型。"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ResultDcaSummary(Base):
    __tablename__ = "result_dca_summary"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    invest_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_invested: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    final_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_return_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    annualized_return: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    max_drawdown: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    invest_count: Mapped[int] = mapped_column(Integer, nullable=False)


class ResultMa120Summary(Base):
    """MA120 策略回测汇总指标。"""

    __tablename__ = "result_ma120_summary"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    capital_mode: Mapped[str] = mapped_column(String(16), nullable=False)  # fixed/recurring/hybrid
    principal: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    monthly_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    splits: Mapped[int] = mapped_column(Integer, nullable=False)
    ma_period: Mapped[int] = mapped_column(Integer, nullable=False)
    buy_threshold: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    step: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    sell_mode: Mapped[str] = mapped_column(String(8), nullable=False)  # batch/all/half
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
    dividend_total: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    win_rate: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)  # 胜率(%)
