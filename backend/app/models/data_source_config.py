"""数据源单行配置模型（Tushare 开关 + Token）。

恒为 ``id=1`` 的单行配置，开关状态与 Token 均落库持久化，重启服务 / 容器不丢失。
"""

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class DataSourceConfig(Base):
    __tablename__ = "data_source_config"

    id: Mapped[int] = mapped_column(TINYINT, primary_key=True, autoincrement=False)
    tushare_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tushare_token: Mapped[str | None] = mapped_column(String(128), nullable=True)
