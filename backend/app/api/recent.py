"""最近回测记录接口（首页用）。

读 ``recent_saves`` 日志表（仅「手动保存」POST /{strategy} 写入），按 ``saved_at`` 倒序取最近 N 条；
return_rate / 起止日期再按 task_id 回查对应策略的 summary 表。

> 只展示手动保存，旧的「回测即落库」历史不在其中，避免被单一策略刷屏。
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.drawboard import ResultDrawboardSummary
from ..models.grid import ResultGridSummary
from ..models.recent import RecentSave
from ..models.result import ResultDcaSummary, ResultMa120Summary
from ..schemas.common import ApiResponse
from ..schemas.recent import RecentBacktestItem
from ..services.symbol_catalog import lookup_name

router = APIRouter()

# type → summary 表 ORM（回查 return_rate / 起止日期）
_SUMMARY = {
    "dca": ResultDcaSummary,
    "ma120": ResultMa120Summary,
    "drawboard": ResultDrawboardSummary,
    "grid": ResultGridSummary,
}


def _relative(saved_at: datetime) -> str:
    """保存时间的相对文案（刚刚 / X分钟前 / X小时前 / X天前）。"""
    # MySQL DATETIME 不存时区，读回为 naive；写入时用的是 UTC，这里补回 tzinfo 再相减
    if saved_at.tzinfo is None:
        saved_at = saved_at.replace(tzinfo=UTC)
    secs = int((datetime.now(UTC) - saved_at).total_seconds())
    if secs < 60:
        return "刚刚"
    if secs < 3600:
        return f"{secs // 60} 分钟前"
    if secs < 86400:
        return f"{secs // 3600} 小时前"
    return f"{secs // 86400} 天前"


@router.get("/recent", response_model=ApiResponse)
def list_recent(limit: int = 5, db: Session = Depends(get_db)) -> ApiResponse:
    """最近 limit 条「手动保存」的回测记录（按保存时间倒序）。"""
    limit = max(1, min(limit, 20))
    rows = (
        db.execute(
            select(RecentSave)
            .order_by(RecentSave.saved_at.desc(), RecentSave.task_id)
            .limit(limit)
        )
        .scalars()
        .all()
    )

    data: list[RecentBacktestItem] = []
    for r in rows:
        rate, start, end = 0.0, None, None
        model = _SUMMARY.get(r.type)
        if model is not None:
            s = db.get(model, r.task_id)
            if s is not None:
                rate = float(s.total_return_rate)
                start, end = s.start_date, s.end_date
        data.append(
            RecentBacktestItem(
                task_id=r.task_id,
                type=r.type,
                symbol=r.symbol,
                symbol_name=lookup_name(r.symbol),
                return_rate=rate,
                period_text=f"{start} ~ {end}" if start and end else "—",
                created_text=_relative(r.saved_at),
            )
        )
    return ApiResponse.ok(data=data)
