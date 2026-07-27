"""指数估值日序列 + 指数注册表（024 估值看板 v2）。

- ``RawIndexValuationDaily``：指数 PE/PB/股息率日序列（lg + csindex 双源统一存此表）。
  与行情 / 资金流语义独立，单独建表（沿用 009/012/016 隔离思路）。
- ``IndexRegistry``：指数注册（替代 016 硬编码 ``_INDEX_NAMES``），含 supported 灰显信息。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import TIMESTAMP, Boolean, Date, Index, Integer, Numeric, String, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RawIndexValuationDaily(Base):
    """指数估值日序列。PE-TTM 为核心列，PB / 股息率按数据源可得性 NULL。"""

    __tablename__ = "raw_index_valuation_daily"
    __table_args__ = (
        Index("idx_index_date", "index_code", "trade_date"),
    )

    index_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    trade_date: Mapped[date] = mapped_column(Date, primary_key=True)
    pe_ttm: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    pb: Mapped[Decimal | None] = mapped_column(Numeric(12, 4), nullable=True)
    dividend_yield: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_at: Mapped[date | None] = mapped_column(
        TIMESTAMP,
        nullable=True,
        server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"),
    )


class IndexRegistry(Base):
    """指数注册表：12 个预置指数，7 个本期可用、5 个灰显禁选。"""

    __tablename__ = "index_registry"

    index_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name_cn: Mapped[str] = mapped_column(String(32), nullable=False)
    lg_name: Mapped[str | None] = mapped_column(String(32), nullable=True)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)  # lg/csindex/none
    supported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    note: Mapped[str | None] = mapped_column(String(160), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
