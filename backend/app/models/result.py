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
