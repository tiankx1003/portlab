"""主题模板 + 标的池模型（事件冲击产业链看板，018）。

- ``theme``：可复用的主题模板（如「新茶饮产业链」），含关键词供智能匹配召回。
- ``theme_stock``：主题模板的标的池，含产业链角色（上/中/下游）+ 权重。
- ``event_stock``：事件实例标的池，创建事件时从主题复制，用户可在事件上增删而不污染模板。
"""

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Theme(Base):
    __tablename__ = "theme"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    keywords: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_builtin: Mapped[bool] = mapped_column(TINYINT(1), nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ThemeStock(Base):
    __tablename__ = "theme_stock"
    __table_args__ = (
        UniqueConstraint("theme_id", "symbol", name="uk_theme_stock_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    theme_id: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    chain_role: Mapped[str] = mapped_column(String(16), nullable=False)
    weight: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("1.00"))


class EventStock(Base):
    __tablename__ = "event_stock"
    __table_args__ = (
        UniqueConstraint("event_id", "symbol", name="uk_event_stock_symbol"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    chain_role: Mapped[str] = mapped_column(String(16), nullable=False)
