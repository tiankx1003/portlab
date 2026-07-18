"""更新日志（Release Notes）数据模型。

由后端 / 运营维护，前端只读展示。每条记录一次产品迭代（新功能 / 修复 / 优化 / 公告）。
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ReleaseNote(Base):
    __tablename__ = "release_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)  # 一句话摘要
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # 类型：feature/bugfix/...
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # 详情 Markdown，可空
    released_at: Mapped[date] = mapped_column(Date, nullable=False)  # 发布日期（业务日期）
    # server_default 使 create_all 建出的列带 DB 级默认值，与 init/04 DDL 一致
    is_deleted: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # 记录创建时间（UTC）
