"""大模型连接配置（单行，事件冲击产业链看板 018 专属）。

恒为 ``id=1`` 的单行配置：API 地址 / Key / 模型名 + 启用开关，落库持久化，重启不丢。
与 009 的 ``data_source_config`` 同构（单行配置表范式），但独立，专供智能匹配使用。

安全说明：当前无鉴权，api_key 明文存储（与 009 tushare_token 一致）；
GET 接口返回掩码（仅后 4 位）。
"""

from datetime import datetime

from sqlalchemy import TIMESTAMP, String, func
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class LlmConfig(Base):
    __tablename__ = "llm_config"

    id: Mapped[int] = mapped_column(TINYINT, primary_key=True, autoincrement=False)
    api_base: Mapped[str | None] = mapped_column(String(255), nullable=True)
    api_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(TINYINT(1), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP,
        server_default=func.current_timestamp(),
        server_onupdate=func.current_timestamp(),
        nullable=False,
    )
