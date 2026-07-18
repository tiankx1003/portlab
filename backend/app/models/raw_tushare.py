"""Tushare 原始行情数据模型。

与 ``raw_price_daily``（AkShare）物理隔离，便于两源数据互不污染、可分别比对。
字段与 ``RawPriceDaily`` 完全一致，仅表名不同。
"""

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RawPriceDailyTushare(Base):
    __tablename__ = "raw_price_daily_tushare"

    symbol: Mapped[str] = mapped_column(String(32), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    open: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    close: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    high: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    low: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    volume: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
