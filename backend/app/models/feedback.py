"""问题反馈数据模型。"""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class Feedback(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown 内容
    nickname: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # UTC
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)  # created_at + 3 天
    is_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 软删除 0/1
