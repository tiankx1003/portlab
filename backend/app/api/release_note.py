"""更新日志接口（只读）。一期仅 GET，数据通过 SQL 维护。

路由前缀 ``/api/release-notes``，返回最新 5 条（未删除），按发布日期倒序。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.release_note import ReleaseNote
from ..schemas.common import ApiResponse
from ..schemas.release_note import ReleaseNoteItem

router = APIRouter()

# 首页 / 面板只展示最新 5 条
_LIST_LIMIT = 5


@router.get("", response_model=ApiResponse)
def list_release_notes(db: Session = Depends(get_db)) -> ApiResponse:
    """最新 5 条更新日志（未删除），按 released_at DESC, id DESC。"""
    rows = (
        db.execute(
            select(ReleaseNote)
            .where(ReleaseNote.is_deleted == 0)
            .order_by(ReleaseNote.released_at.desc(), ReleaseNote.id.desc())
            .limit(_LIST_LIMIT)
        )
        .scalars()
        .all()
    )
    data = [
        ReleaseNoteItem(
            id=r.id,
            title=r.title,
            type=r.type,
            detail=r.detail,
            released_at=r.released_at,
        )
        for r in rows
    ]
    return ApiResponse.ok(data=data)
