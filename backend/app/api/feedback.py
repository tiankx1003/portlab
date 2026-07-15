"""问题反馈接口。

- POST   /api/feedback        提交反馈（自动清过期 + 超 5 条删最早）
- GET    /api/feedback        有效反馈列表（未删除 + 未过期，倒序）
- DELETE /api/feedback/{id}   软删除指定反馈

时间统一用 UTC（naive）存储与比较，避免依赖 MySQL 服务器时区。
"""

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.feedback import Feedback
from ..schemas.common import ApiResponse
from ..schemas.feedback import FeedbackCreate, FeedbackCreated, FeedbackItem

router = APIRouter()

FEEDBACK_TTL = timedelta(days=3)
MAX_FEEDBACK = 5


def _utcnow() -> datetime:
    """当前 UTC 时间（naive，与表中 DATETIME 一致）。"""
    return datetime.now(UTC).replace(tzinfo=None)


def _active_filter(now: datetime):
    return (Feedback.is_deleted == 0) & (Feedback.expires_at > now)


@router.post("", response_model=ApiResponse)
def create_feedback(req: FeedbackCreate, db: Session = Depends(get_db)) -> ApiResponse:
    now = _utcnow()
    # 提交时清理已过期记录（软删除）
    db.execute(
        update(Feedback)
        .where(Feedback.is_deleted == 0, Feedback.expires_at <= now)
        .values(is_deleted=1)
    )

    fb = Feedback(
        content=req.content,
        nickname=req.nickname.strip() if req.nickname else None,
        created_at=now,
        expires_at=now + FEEDBACK_TTL,
    )
    db.add(fb)
    db.flush()  # 取自增 id

    _enforce_max(db, now)
    db.commit()
    return ApiResponse.ok(data=FeedbackCreated(id=fb.id))


def _enforce_max(db: Session, now: datetime) -> None:
    """有效反馈超过 MAX_FEEDBACK 条时，软删除最早的（保留最新 MAX_FEEDBACK 条）。"""
    active_ids = (
        db.execute(
            select(Feedback.id)
            .where(_active_filter(now))
            .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        )
        .scalars()
        .all()
    )
    if len(active_ids) > MAX_FEEDBACK:
        stale = active_ids[MAX_FEEDBACK:]
        if stale:
            db.execute(update(Feedback).where(Feedback.id.in_(stale)).values(is_deleted=1))


@router.get("", response_model=ApiResponse)
def list_feedback(db: Session = Depends(get_db)) -> ApiResponse:
    now = _utcnow()
    rows = (
        db.execute(
            select(Feedback)
            .where(_active_filter(now))
            .order_by(Feedback.created_at.desc(), Feedback.id.desc())
        )
        .scalars()
        .all()
    )
    data = [
        FeedbackItem(
            id=r.id, content=r.content, nickname=r.nickname,
            created_at=r.created_at, expires_at=r.expires_at,
        )
        for r in rows
    ]
    return ApiResponse.ok(data=data)


@router.delete("/{fb_id}", response_model=ApiResponse)
def delete_feedback(fb_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    fb = db.get(Feedback, fb_id)
    if fb is None:
        return ApiResponse.error(message="反馈不存在")
    if not fb.is_deleted:
        fb.is_deleted = 1
        db.commit()
    return ApiResponse.ok()
