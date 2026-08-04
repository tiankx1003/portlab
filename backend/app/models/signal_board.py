"""估值与信号看板的原始数据模型（032）。

- ``RawBondYieldDaily``：十年期国债收益率日序列（``bond_zh_us_rate`` 中债 10 年）。
- ``RawIndexDaily``：指数日线收盘点位（价格 + 全收益共存；右轴/均值之锚用）。
- ``RawMacroIndicator``：宏观指标月/日序列（generic 表，Tushare）。
- ``RawMarginBalance``：融资融券余额（交易所级汇总，Tushare）。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Date, Index, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RawBondYieldDaily(Base):
    """十年期国债收益率日序列（%）。"""

    __tablename__ = "raw_bond_yield_daily"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    yield_10y: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), nullable=True)
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'bond_zh_us_rate'")
    )
    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class RawIndexDaily(Base):
    """指数日线收盘点位（价格 + 全收益共存）。"""

    __tablename__ = "raw_index_daily"
    __table_args__ = (Index("idx_index_date", "index_code", "trade_date"),)

    index_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    index_type: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'price'")
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'akshare_daily'")
    )
    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class RawMacroIndicator(Base):
    """宏观指标月/日序列（generic 表，Tushare）。"""

    __tablename__ = "raw_macro_indicator"

    indicator: Mapped[str] = mapped_column(String(32), primary_key=True)
    ref_date: Mapped[date] = mapped_column(Date, primary_key=True)
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'tushare'")
    )
    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class RawMarginBalance(Base):
    """融资融券余额（交易所级汇总，Tushare）。"""

    __tablename__ = "raw_margin_balance"

    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    rzye: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    rqye: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    source: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=text("'tushare'")
    )
    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )
