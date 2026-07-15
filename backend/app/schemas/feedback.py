"""问题反馈相关 schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000, description="反馈内容（Markdown）")
    nickname: str | None = Field(None, max_length=64, description="可选昵称")


class FeedbackItem(BaseModel):
    id: int
    content: str
    nickname: str | None
    created_at: datetime
    expires_at: datetime


class FeedbackCreated(BaseModel):
    id: int
