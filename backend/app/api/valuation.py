"""估值看板 v2 接口（024）。

- GET ``/api/valuation/indices``：返回 index_registry（12 项，含 supported/note）。
- GET ``/api/valuation/single``：单指数 ensure → 通道+分位 → SingleValuationData。
- GET ``/api/valuation/overlay``：多指数 ensure → 共同交易日归一化 → OverlayData。
- GET ``/api/valuation?symbol=``：016 旧端点，内部转发 single(all) 并映射为旧形态（向后兼容）。
"""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.common import ApiResponse
from ..services.valuation_data import (
    build_overlay_valuation,
    build_single_valuation,
    list_indices,
)

router = APIRouter()


@router.get("/indices", response_model=ApiResponse)
def indices(db: Session = Depends(get_db)) -> ApiResponse:
    """指数下拉项（含 supported 灰显 + note 说明）。"""
    return ApiResponse.ok(data={"items": list_indices(db)})


@router.get("/single", response_model=ApiResponse)
def single(
    symbol: str = Query(..., min_length=1, max_length=16),
    lookback: str = "5y",
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """单指数 PE 通道 + 历史分位。supported=false 时返回 note，不报错。"""
    return ApiResponse.ok(
        data=build_single_valuation(db, symbol, lookback, start_date, end_date)
    )


@router.get("/overlay", response_model=ApiResponse)
def overlay(
    symbols: str = Query(..., description="逗号分隔的指数代码，如 000300,000852"),
    lookback: str = "5y",
    base: int = Query(1, ge=1, le=1000),
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """多指数叠加：取共同交易日，PE-TTM 归一化（起点 = base）。"""
    syms = [s.strip() for s in symbols.split(",") if s.strip()]
    if not syms:
        return ApiResponse.error(message="请至少选择一个指数")
    return ApiResponse.ok(
        data=build_overlay_valuation(db, syms, lookback, base, start_date, end_date)
    )


@router.get("", response_model=ApiResponse)
def valuation(symbol: str = "000300", db: Session = Depends(get_db)) -> ApiResponse:
    """016 旧端点（向后兼容）：内部转发 single(lookback=all) 并映射为旧形态。

    顺带修复 016 的 ``创业板指`` KeyError——现在 unsupported 指数返回 available=false + note。
    """
    data = build_single_valuation(db, symbol, "all", None, None)
    return ApiResponse.ok(data=_to_legacy(data))


def _to_legacy(d: dict) -> dict:
    """SingleValuationData → 016 旧形态（available/reason/series:[date,pe]）。"""
    if not d.get("available"):
        return {"available": False, "reason": d.get("note") or d.get("fetch_warning") or "暂无数据"}
    dates = d["dates"]
    pe = d["pe_ttm"]
    series = [[dates[i], pe[i]] for i in range(len(dates)) if pe[i] is not None]
    ch = d.get("channel") or {}
    return {
        "available": True,
        "symbol": d["index_code"],
        "name": d["name_cn"],
        "current_pe": d.get("current_pe"),
        "percentile": d.get("percentile"),
        "min": ch.get("l1_min"),
        "max": ch.get("l5_max"),
        "as_of": d.get("as_of"),
        "series": series[-300:],
    }
