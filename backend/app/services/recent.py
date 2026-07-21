"""最近回测保存日志服务。

`log_save` 在每个策略的「保存」端点（POST /{strategy}）成功后调用，
幂等 upsert：重复保存同一参数刷新 ``saved_at``（重新置顶）。
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from ..models.recent import RecentSave


def log_save(db: Session, task_id: str, btype: str, symbol: str) -> None:
    """记录一次手动保存。已存在则刷新 saved_at，使最近记录按真实保存时间排序。"""
    row = db.get(RecentSave, task_id)
    now = datetime.now(UTC)
    if row is None:
        db.add(RecentSave(task_id=task_id, type=btype, symbol=symbol, saved_at=now))
    else:
        row.type = btype
        row.symbol = symbol
        row.saved_at = now
    db.commit()
