"""定投回测逐日计算结果模型。"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class CalcDcaBacktest(Base):
    __tablename__ = "calc_dca_backtest"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    is_invest_day: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # 0/1
    buy_shares: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cum_shares: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    cum_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    market_value: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    pnl: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    return_rate: Mapped[Decimal] = mapped_column(Numeric(12, 4), nullable=False)
    # 智能定投相关（普通模式：invest 日为 1.0000 / 设定金额，非 invest 日为 NULL）
    deduction_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    actual_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
