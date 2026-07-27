"""指数估值数据保障 + 看板编排（024 估值看板 v2）。

- ``ensure_valuation``：先查本地 → 仅补缺失区间 → UPSERT 幂等（与 007/009/012 同构）；
  csindex 另做股息率当日快照覆盖式刷新（仅更新 dividend_yield 列）。
- ``build_single_valuation`` / ``build_overlay_valuation``：单指数通道+分位、多指数归一化。
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.valuation import IndexRegistry, RawIndexValuationDaily
from .compute.valuation_metrics import (
    channel_position,
    normalize_to_base,
    pe_channel,
    percentile_rank,
)
from .fetcher import FetchError
from .fetcher.valuation_fetcher import ValuationBar, fetch_csindex_dividend, fetch_valuation
from .storage import upsert_dividend_snapshot, upsert_valuation

logger = logging.getLogger(__name__)

# 起点端假期容差；尾端数据刷新阈值（避免每次请求都重拉全量）
FRONT_TOL = timedelta(days=7)
BACK_TOL = timedelta(days=3)

_LOOKBACK_DAYS = {"1y": 365, "3y": 1095, "5y": 1825, "7y": 2555, "10y": 3650}
# 「成立以来」回看拉取起点（lg 数据始于 2005；csindex 按各自成立日返回）
_EARLY_START = date(2005, 1, 1)


# ---- 注册表 ----

def list_indices(db: Session) -> list[dict]:
    """返回注册表（含 supported / note），前端渲染下拉用。"""
    rows = db.execute(
        select(IndexRegistry).order_by(IndexRegistry.sort_order, IndexRegistry.index_code)
    ).scalars().all()
    return [
        {
            "index_code": r.index_code,
            "name_cn": r.name_cn,
            "lg_name": r.lg_name,
            "source_type": r.source_type,
            "supported": bool(r.supported),
            "note": r.note,
            "sort_order": r.sort_order,
        }
        for r in rows
    ]


def get_registry(db: Session, index_code: str) -> IndexRegistry | None:
    return db.get(IndexRegistry, index_code)


# ---- 数据保障（ensure）----

def _range_stats(db: Session, index_code: str) -> tuple[date | None, date | None, int]:
    row = db.execute(
        select(
            func.min(RawIndexValuationDaily.trade_date),
            func.max(RawIndexValuationDaily.trade_date),
            func.count(),
        ).where(RawIndexValuationDaily.index_code == index_code)
    ).one()
    return row[0], row[1], row[2]


def ensure_valuation(
    db: Session,
    index_code: str,
    source_type: str,
    lg_name: str | None,
    start: date,
    end: date,
) -> str | None:
    """确保 [start, end] 区间估值数据完整；csindex 另刷股息率快照。返回错误信息或 None。"""
    errors: list[str] = []
    min_d, max_d, cnt = _range_stats(db, index_code)

    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    else:
        if min_d and min_d > start + FRONT_TOL:
            ranges.append((start, min_d))  # 前段缺失：拉到已有最早日（含，UPSERT 幂等）
        if max_d and end - max_d > BACK_TOL:
            ranges.append((max_d, end))  # 尾段缺失/有新数据：从已有最晚日（含）拉到 end

    for s, e in ranges:
        try:
            bars = fetch_valuation(index_code, source_type, lg_name, s, e)
        except FetchError as ex:
            errors.append(str(ex))
        except Exception as ex:  # noqa: BLE001
            errors.append(str(ex))
        else:
            upsert_valuation(db, bars)

    # csindex 股息率快照：每次请求刷新最新一日（覆盖式，仅更新 dividend_yield 列）；
    # 已有当日快照（BACK_TOL 内）则跳过，避免每页加载都打远端。
    if source_type == "csindex":
        _refresh_csindex_dividend(db, index_code, end, errors)

    return errors[0] if errors else None


def _refresh_csindex_dividend(
    db: Session, index_code: str, end: date, errors: list[str]
) -> None:
    """csindex 股息率当日快照覆盖式刷新（仅 dividend_yield 列，不触碰 pe/pb）。"""
    div_row = db.execute(
        select(func.max(RawIndexValuationDaily.trade_date)).where(
            RawIndexValuationDaily.index_code == index_code,
            RawIndexValuationDaily.dividend_yield.is_not(None),
        )
    ).scalar()
    if div_row and end - div_row <= BACK_TOL:
        return  # 当日快照已新鲜，跳过远端拉取

    try:
        div_map = fetch_csindex_dividend(index_code)
    except Exception as ex:  # noqa: BLE001
        errors.append(f"股息率快照刷新失败：{ex}")
        return
    if not div_map:
        return
    latest = max(div_map)
    val = div_map[latest]
    if val is None:
        return
    from .fetcher.valuation_fetcher import _to_dec  # noqa: PLC0415 - 复用宽松转换

    upsert_dividend_snapshot(db, index_code, latest, _to_dec(val))


# ---- 读取 ----

def read_series(
    db: Session, index_code: str, start: date, end: date
) -> list[ValuationBar]:
    """读取 [start, end] 区间估值序列（按日期升序）。"""
    rows = db.execute(
        select(RawIndexValuationDaily)
        .where(
            RawIndexValuationDaily.index_code == index_code,
            RawIndexValuationDaily.trade_date >= start,
            RawIndexValuationDaily.trade_date <= end,
        )
        .order_by(RawIndexValuationDaily.trade_date)
    ).scalars().all()
    return [
        ValuationBar(
            index_code=r.index_code,
            trade_date=r.trade_date,
            pe_ttm=r.pe_ttm,
            pb=r.pb,
            dividend_yield=r.dividend_yield,
            source=r.source,
        )
        for r in rows
    ]


def _resolve_window(
    lookback: str, start_date: date | None, end_date: date | None
) -> tuple[date, date]:
    end = end_date or date.today()
    if start_date:
        return start_date, end
    if lookback == "all":
        return _EARLY_START, end
    return end - timedelta(days=_LOOKBACK_DAYS[lookback]), end


def _to_float(v: Decimal | None) -> float | None:
    return None if v is None else float(v)


# ---- 单指数编排 ----

def build_single_valuation(
    db: Session,
    index_code: str,
    lookback: str,
    start_date: date | None,
    end_date: date | None,
) -> dict:
    """单指数：ensure → 按窗口算通道+分位 → SingleValuationData。"""
    reg = get_registry(db, index_code)
    base = {
        "index_code": index_code,
        "name_cn": reg.name_cn if reg else index_code,
        "source_type": reg.source_type if reg else "none",
        "supported": bool(reg.supported) if reg else False,
    }
    if reg is None:
        return {"available": False, **base, "note": f"未知指数代码：{index_code}"}
    if not reg.supported:
        return {"available": False, **base, "note": reg.note}

    start, end = _resolve_window(lookback, start_date, end_date)
    err = ensure_valuation(db, index_code, reg.source_type, reg.lg_name, start, end)
    bars = read_series(db, index_code, start, end)
    if not bars:
        return {"available": False, **base, "note": err or "该指数暂无估值数据"}

    dates = [b.trade_date.isoformat() for b in bars]
    pe = [_to_float(b.pe_ttm) for b in bars]
    pb = [_to_float(b.pb) for b in bars]

    pe_valid = [p for p in pe if p is not None]
    channel = pe_channel(pe)
    current_pe = pe_valid[-1] if pe_valid else None
    percentile = percentile_rank(current_pe, pe_valid) if current_pe is not None else None

    pb_valid = [p for p in pb if p is not None]
    current_pb = pb_valid[-1] if pb_valid else None

    divs = [(_to_float(b.dividend_yield)) for b in bars if b.dividend_yield is not None]
    current_div = divs[-1] if divs else None

    return {
        "available": True,
        **base,
        "dates": dates,
        "pe_ttm": pe,
        "pb": pb,
        "channel": channel,
        "current_pe": current_pe,
        "percentile": percentile,
        "channel_position": channel_position(current_pe, channel),
        "current_pb": current_pb,
        "dividend_yield": current_div,
        "pb_available": reg.source_type == "lg" and current_pb is not None,
        "dividend_available": reg.source_type == "csindex" and current_div is not None,
        "as_of": dates[-1],
        "fetch_warning": err,  # 数据已部分可用但补缺失败时透出（不阻断展示）
    }


# ---- 多指数叠加编排 ----

def build_overlay_valuation(
    db: Session,
    symbols: list[str],
    lookback: str,
    base: int,
    start_date: date | None,
    end_date: date | None,
) -> dict:
    """多指数：ensure 各指数 → 取共同交易日 → 归一化 → OverlayData。

    归一化对象为 PE-TTM（估值看板核心指标；存储层仅持久化 PE，无指数点位）。
    """
    start, end = _resolve_window(lookback, start_date, end_date)
    per_index: dict[str, dict[str, float]] = {}
    names: dict[str, str] = {}
    for sym in symbols:
        reg = get_registry(db, sym)
        if reg is None or not reg.supported:
            continue
        ensure_valuation(db, sym, reg.source_type, reg.lg_name, start, end)
        bars = read_series(db, sym, start, end)
        if not bars:
            continue
        per_index[sym] = {
            b.trade_date.isoformat(): p for b in bars if (p := _to_float(b.pe_ttm)) is not None
        }
        names[sym] = reg.name_cn

    series = []
    if per_index:
        date_sets = [set(m.keys()) for m in per_index.values()]
        common = (
            sorted(set.intersection(*date_sets)) if len(date_sets) > 1 else sorted(date_sets[0])
        )
        for sym, m in per_index.items():
            pe_list = [m.get(d) for d in common]
            series.append(
                {
                    "index_code": sym,
                    "name_cn": names[sym],
                    "normalized": normalize_to_base(pe_list, float(base)),
                }
            )
        return {"base": base, "dates": common, "series": series}

    return {
        "base": base,
        "dates": [],
        "series": [],
        "note": "所选指数无可叠加的 PE 数据（请勾选本期支持的指数）",
    }
