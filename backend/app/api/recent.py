"""最近回测记录接口（首页用）。

合并 DCA（result_dca_summary）与 MA120（result_ma120_summary）两表，按 end_date 倒序取最近 N 条。

> 两表均无 created_at 列，task_id 为 PK 且编码起止日期。一期以 ``end_date DESC`` 作为
> 「记录时间近似值」排序基准（回测结束日越近越靠前），非真正创建时间；精确创建时间需后续给
> 两表加 created_at 列（见 011 开放问题）。
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.result import ResultDcaSummary, ResultMa120Summary
from ..schemas.common import ApiResponse
from ..schemas.recent import RecentBacktestItem
from ..services.symbol_catalog import lookup_name

router = APIRouter()


@router.get("/recent", response_model=ApiResponse)
def list_recent(limit: int = 5, db: Session = Depends(get_db)) -> ApiResponse:
    """最近 limit 条回测记录（合并 DCA + MA120，按 end_date 倒序）。"""
    limit = max(1, min(limit, 20))

    # (type, task_id, symbol, return_rate, start_date, end_date)
    merged: list[tuple[str, str, str, float, date, date]] = []

    for r in db.execute(
        select(
            ResultDcaSummary.task_id,
            ResultDcaSummary.symbol,
            ResultDcaSummary.total_return_rate,
            ResultDcaSummary.start_date,
            ResultDcaSummary.end_date,
        )
    ).all():
        merged.append(("dca", r.task_id, r.symbol, float(r.total_return_rate),
                       r.start_date, r.end_date))

    for r in db.execute(
        select(
            ResultMa120Summary.task_id,
            ResultMa120Summary.symbol,
            ResultMa120Summary.total_return_rate,
            ResultMa120Summary.start_date,
            ResultMa120Summary.end_date,
        )
    ).all():
        merged.append(("ma120", r.task_id, r.symbol, float(r.total_return_rate),
                       r.start_date, r.end_date))

    # end_date 倒序（同日再按 task_id 稳定排序）
    merged.sort(key=lambda x: (x[5], x[1]), reverse=True)
    merged = merged[:limit]

    data = [
        RecentBacktestItem(
            task_id=task_id,
            type=btype,
            symbol=symbol,
            symbol_name=lookup_name(symbol),
            return_rate=rate,
            period_text=f"{start} ~ {end}",
            created_text=str(end),
        )
        for btype, task_id, symbol, rate, start, end in merged
    ]
    return ApiResponse.ok(data=data)
