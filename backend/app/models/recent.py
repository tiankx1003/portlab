"""最近回测保存日志模型（首页「最近回测记录」用）。

只记录「手动保存」（POST /{strategy}）事件，按 ``saved_at`` 倒序展示；
旧的「回测即落库」历史不在其中，避免被单一策略刷屏。
"""

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class RecentSave(Base):
    __tablename__ = "recent_saves"

    task_id: Mapped[str] = mapped_column(String(96), primary_key=True)
    type: Mapped[str] = mapped_column(String(16), nullable=False)  # dca/ma120/drawboard/grid
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    saved_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
