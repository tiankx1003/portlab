"""更新日志相关 schema（前端只读展示）。"""

from datetime import date

from pydantic import BaseModel


class ReleaseNoteItem(BaseModel):
    id: int
    title: str
    type: str  # feature / bugfix / improvement / notice
    detail: str | None  # Markdown 原文，前端渲染
    released_at: date
