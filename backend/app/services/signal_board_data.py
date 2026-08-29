"""估值与信号看板编排（032）：三层共振信号体系。

- ``ensure_*``：数据保障（先查本地→补缺口→UPSERT 幂等），复用 002/024 范式。
- ``build_target_signals``：第一层，单标的多维信号（技术 + 估值）。
- ``build_market_signals``：第二层，大类资产估值（全收益均线 + 股债比价 + 比值 + 发行热度）。
- ``build_capital_macro_signals``：第三层，资金 + 宏观（全 Tushare，token 缺失降级）。
- ``build_resonance``：三层共振汇总。

数据源：第一二层走 AkShare（国债/指数点位/PE），第三层走 Tushare（宏观/融资融券/北向/份额）。
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.signal_board import (
    RawBondYieldDaily,
    RawCommodityDaily,
    RawIndexDaily,
    RawMacroIndicator,
    RawMarginBalance,
)
from ..models.valuation import IndexRegistry, RawIndexValuationDaily
from .compute.equity_bond_metrics import channel_position, rolling_channel
from .compute.signal_light import (
    Light,
    light_drawdown,
    light_equity_bond,
    light_fund_issue,
    light_ma120_deviation,
    light_macro,
    light_margin_percentile,
    light_mean_anchor,
    light_pe_percentile,
    layer_summary,
    resonance as resonance_fn,
)
from .compute.valuation_metrics import percentile_rank
from .fetcher import FetchError
from .fetcher.commodity_fetcher import fetch_commodity, list_commodity_symbols
from .fetcher.macro_fetcher import fetch_fund_issue, fetch_macro, fetch_margin, fetch_northbound
from .fetcher.signal_fetcher import fetch_bond_yield, fetch_index_close, fetch_total_return_close
from .storage import (
    upsert_bond_yield,
    upsert_commodity,
    upsert_index_close,
    upsert_macro,
    upsert_margin,
)
from .valuation_data import ensure_valuation, get_registry, read_series

logger = logging.getLogger(__name__)

FRONT_TOL = timedelta(days=7)
BACK_TOL = timedelta(days=3)

# ETF → 跟踪指数映射（本期硬编码核心标的）
# (index_code, index_name, etf_name)
_ETF_INDEX_MAP: dict[str, tuple[str, str, str]] = {
    "510300": ("000300", "沪深300", "华泰柏瑞沪深300ETF"),
    "510050": ("000016", "上证50", "华夏上证50ETF"),
    "510500": ("000905", "中证500", "南方中证500ETF"),
    "510880": ("000015", "上证红利", "华泰柏瑞上证红利ETF"),
    "512890": ("H30269", "中证红利低波动", "华泰柏瑞红利低波ETF"),
    "515080": ("000922", "中证红利", "招商中证红利ETF"),
    "515360": ("000300", "沪深300", "方正富邦沪深300ETF"),
    "513920": ("000922", "中证红利", "华泰柏瑞港股央企红利ETF"),
}

_LOOKBACK_DAYS = {"1y": 365, "3y": 1095, "5y": 1825, "10y": 3650}


def _resolve_window(lookback: str) -> tuple[date, date]:
    end = date.today()
    days = _LOOKBACK_DAYS.get(lookback, 1825)
    return end - timedelta(days=days), end


def _resolve_symbol(symbol: str) -> tuple[str, str, str]:
    """解析标的 → (index_code, etf_or_symbol_name, index_name)。

    - ETF 代码：返回 (跟踪指数代码, ETF 名称, 指数名称)
    - 指数代码直传：返回 (指数代码, 指数名称, 指数名称)（两者相同）
    """
    if symbol in _ETF_INDEX_MAP:
        index_code, index_name, etf_name = _ETF_INDEX_MAP[symbol]
        return index_code, etf_name, index_name
    # 指数代码直传：查 registry 取名称
    reg_name = {"000300": "沪深300", "000016": "上证50", "000905": "中证500"}.get(symbol, symbol)
    return symbol, reg_name, reg_name


# ---- 数据保障 ----


def _bond_range_stats(db: Session) -> tuple[date | None, date | None, int]:
    row = db.execute(
        select(
            func.min(RawBondYieldDaily.trade_date),
            func.max(RawBondYieldDaily.trade_date),
            func.count(),
        )
    ).one()
    return row[0], row[1], row[2]


def ensure_bond_yield(db: Session, start: date, end: date) -> str | None:
    """确保 [start, end] 区间国债收益率完整。返回错误信息或 None。"""
    min_d, max_d, cnt = _bond_range_stats(db)
    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    else:
        if min_d and min_d > start + FRONT_TOL:
            ranges.append((start, min_d))
        if max_d and end - max_d > BACK_TOL:
            ranges.append((max_d, end))
    for s, e in ranges:
        try:
            bars = fetch_bond_yield(s, e)
            upsert_bond_yield(db, bars)
        except FetchError as ex:
            return str(ex)
        except Exception as ex:  # noqa: BLE001
            return str(ex)
    return None


def _index_range_stats(db: Session, index_code: str) -> tuple[date | None, date | None, int]:
    row = db.execute(
        select(
            func.min(RawIndexDaily.trade_date),
            func.max(RawIndexDaily.trade_date),
            func.count(),
        ).where(RawIndexDaily.index_code == index_code)
    ).one()
    return row[0], row[1], row[2]


def ensure_index_close(db: Session, index_code: str, start: date, end: date, total_return: bool = False) -> str | None:
    """确保 [start, end] 区间指数点位完整（价格或全收益）。"""
    min_d, max_d, cnt = _index_range_stats(db, index_code)
    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    else:
        if min_d and min_d > start + FRONT_TOL:
            ranges.append((start, min_d))
        if max_d and end - max_d > BACK_TOL:
            ranges.append((max_d, end))
    for s, e in ranges:
        try:
            if total_return:
                bars = fetch_total_return_close(index_code, s, e)
            else:
                bars = fetch_index_close(index_code, s, e)
            upsert_index_close(db, bars)
        except FetchError as ex:
            return str(ex)
        except Exception as ex:  # noqa: BLE001
            return str(ex)
    return None


def _read_bond(db: Session, start: date, end: date) -> list[tuple[date, float]]:
    rows = db.execute(
        select(RawBondYieldDaily.trade_date, RawBondYieldDaily.yield_10y)
        .where(RawBondYieldDaily.trade_date >= start, RawBondYieldDaily.trade_date <= end)
        .order_by(RawBondYieldDaily.trade_date)
    ).all()
    return [(r.trade_date, float(r.yield_10y)) for r in rows if r.yield_10y is not None]


def _read_index_close(db: Session, index_code: str, start: date, end: date) -> list[tuple[date, float]]:
    rows = db.execute(
        select(RawIndexDaily.trade_date, RawIndexDaily.close)
        .where(
            RawIndexDaily.index_code == index_code,
            RawIndexDaily.trade_date >= start,
            RawIndexDaily.trade_date <= end,
        )
        .order_by(RawIndexDaily.trade_date)
    ).all()
    return [(r.trade_date, float(r.close)) for r in rows if r.close is not None]


def _read_macro(db: Session, indicator: str, start: date, end: date) -> list[tuple[date, float]]:
    rows = db.execute(
        select(RawMacroIndicator.ref_date, RawMacroIndicator.value)
        .where(
            RawMacroIndicator.indicator == indicator,
            RawMacroIndicator.ref_date >= start,
            RawMacroIndicator.ref_date <= end,
        )
        .order_by(RawMacroIndicator.ref_date)
    ).all()
    return [(r.ref_date, float(r.value)) for r in rows if r.value is not None]


def _read_margin(db: Session, start: date, end: date) -> list[tuple[date, float, float]]:
    rows = db.execute(
        select(RawMarginBalance.trade_date, RawMarginBalance.rzye, RawMarginBalance.rqye)
        .where(RawMarginBalance.trade_date >= start, RawMarginBalance.trade_date <= end)
        .order_by(RawMarginBalance.trade_date)
    ).all()
    return [
        (r.trade_date, float(r.rzye or 0), float(r.rqye or 0)) for r in rows
    ]


_MACRO_FETCH_COOLDOWN: dict[str, float] = {}  # indicator → 上次拉取的 monotonic 时间戳
_COOLDOWN_SECONDS = 3600  # 月频指标 1 小时内不重复拉（Tushare 月频数据有滞后，频繁拉是浪费）


def _ensure_macro(
    db: Session, indicator: str, start: date, end: date, fetch_fn=None,
) -> str | None:
    """确保宏观指标 [start, end] 完整。

    ``fetch_fn`` 默认用 ``fetch_macro``（sf/m1m2/ppi/pmi）；
    北向/基金发行等非 fetch_macro 覆盖的指标，传入对应的 fetch 函数（返回 list[MacroBar]）。

    月频指标有天然滞后（Tushare 月度数据通常月中才更新上月），频繁拉取返回的还是旧数据。
    故加 1 小时进程级冷却：冷却期内即使判定「需补」也跳过远端拉取（命中本地已有数据）。
    """
    import time as _time  # noqa: PLC0415

    fetcher = fetch_fn or fetch_macro
    cnt = db.execute(
        select(func.count()).where(RawMacroIndicator.indicator == indicator)
    ).scalar() or 0
    max_d = db.execute(
        select(func.max(RawMacroIndicator.ref_date)).where(RawMacroIndicator.indicator == indicator)
    ).scalar()
    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    elif max_d and end - max_d > timedelta(days=35):  # 月频容差
        ranges.append((max_d, end))

    if ranges:
        # 冷却检查：1 小时内拉过的月频指标跳过（数据不会变）
        now = _time.monotonic()
        last = _MACRO_FETCH_COOLDOWN.get(indicator, 0)
        if now - last < _COOLDOWN_SECONDS:
            ranges = []  # 冷却中，跳过拉取
        else:
            _MACRO_FETCH_COOLDOWN[indicator] = now

    for s, e in ranges:
        try:
            bars = fetcher(indicator, s, e) if fetch_fn is None else fetcher(s, e)
            upsert_macro(db, bars)
        except FetchError as ex:
            return str(ex)
        except Exception as ex:  # noqa: BLE001
            return str(ex)
    return None


def _ensure_margin(db: Session, start: date, end: date) -> str | None:
    cnt = db.execute(select(func.count()).select_from(RawMarginBalance)).scalar() or 0
    max_d = db.execute(select(func.max(RawMarginBalance.trade_date))).scalar()
    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    elif max_d and end - max_d > BACK_TOL:
        ranges.append((max_d, end))
    for s, e in ranges:
        try:
            rows = fetch_margin(s, e)
            upsert_margin(db, rows)
        except FetchError as ex:
            return str(ex)
        except Exception as ex:  # noqa: BLE001
            return str(ex)
    return None


def ensure_commodity(db: Session, symbol: str, start: date, end: date) -> str | None:
    """确保 [start, end] 区间大宗商品完整。"""
    row = db.execute(
        select(
            func.min(RawCommodityDaily.trade_date),
            func.max(RawCommodityDaily.trade_date),
            func.count(),
        ).where(RawCommodityDaily.symbol == symbol)
    ).one()
    mn, mx, cnt = row[0], row[1], row[2]
    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    else:
        if mn and mn > start + FRONT_TOL:
            ranges.append((start, mn))
        if mx and end - mx > BACK_TOL:
            ranges.append((mx, end))
    for s, e in ranges:
        try:
            bars = fetch_commodity(symbol, s, e)
            upsert_commodity(db, bars)
        except FetchError as ex:
            return str(ex)
        except Exception as ex:  # noqa: BLE001
            return str(ex)
    return None


def _read_commodity(db: Session, symbol: str, start: date, end: date) -> list[tuple[date, float]]:
    rows = db.execute(
        select(RawCommodityDaily.trade_date, RawCommodityDaily.close)
        .where(
            RawCommodityDaily.symbol == symbol,
            RawCommodityDaily.trade_date >= start,
            RawCommodityDaily.trade_date <= end,
        )
        .order_by(RawCommodityDaily.trade_date)
    ).all()
    return [(r.trade_date, float(r.close)) for r in rows if r.close is not None]


def _has_tushare_token() -> bool:
    """检查 Tushare token 是否配置（不抛异常）。"""
    try:
        from .fetcher.tushare_fetcher import _resolve_token  # noqa: PLC0415

        _resolve_token()
        return True
    except Exception:  # noqa: BLE001
        return False


# ---- 第一层：技术 + 估值 ----


def build_target_signals(db: Session, symbol: str, lookback: str) -> dict:
    """单标的多维信号。"""
    index_code, symbol_name, index_name = _resolve_symbol(symbol)
    reg = get_registry(db, index_code)
    start, end = _resolve_window(lookback)

    metrics: list[dict] = []
    warnings: list[str] = []
    lights: list[Light] = []

    # PE/PB（复用 024）
    pe_vals: list[float | None] = []
    pb_vals: list[float | None] = []
    dividend_val: float | None = None
    pe_dates: list[str] = []
    pe_chart_data: dict = {}
    if reg and reg.supported:
        err = ensure_valuation(db, index_code, reg.source_type, reg.lg_name, start, end)
        if err:
            warnings.append(err)
        bars = read_series(db, index_code, start, end)
        pe_dates = [b.trade_date.isoformat() for b in bars]
        pe_vals = [float(b.pe_ttm) if b.pe_ttm else None for b in bars]
        pb_vals = [float(b.pb) if b.pb else None for b in bars]
        pe_valid = [v for v in pe_vals if v is not None]
        current_pe = pe_valid[-1] if pe_valid else None
        pe_pct = percentile_rank(current_pe, pe_valid) if current_pe else None
        lights.append(light_pe_percentile(pe_pct))
        metrics.append({
            "key": "pe", "label": "PE 分位", "value": pe_pct,
            "display": f"{pe_pct:.0f}%" if pe_pct is not None else "—",
            "light": light_pe_percentile(pe_pct),
            "hint": f"当前 PE {current_pe:.1f}" if current_pe else None,
        })
        # PB（仅 lg 源 5 宽基）
        pb_valid = [v for v in pb_vals if v is not None]
        current_pb = pb_valid[-1] if pb_valid else None
        pb_pct = percentile_rank(current_pb, pb_valid) if current_pb else None
        pb_light = light_pe_percentile(pb_pct)
        lights.append(pb_light)
        metrics.append({
            "key": "pb", "label": "PB 分位", "value": pb_pct,
            "display": f"{pb_pct:.0f}%" if pb_pct is not None else "—",
            "light": pb_light,
            "hint": f"当前 PB {current_pb:.2f}" if current_pb else "无数据",
        })
        # 股息率（仅 csindex 快照，降级）
        divs = [float(b.dividend_yield) for b in bars if b.dividend_yield is not None]
        dividend_val = divs[-1] if divs else None
        metrics.append({
            "key": "dividend", "label": "股息率", "value": dividend_val,
            "display": f"{dividend_val:.2f}%" if dividend_val is not None else "—",
            "light": "grey",
            "hint": "仅当日快照" if dividend_val is not None else "无历史序列",
        })
        # PE 通道图表（复用 024 channel 逻辑简化：传 dates + pe）
        from .compute.valuation_metrics import pe_channel  # noqa: PLC0415

        ch = pe_channel(pe_vals)
        pe_chart_data = {"dates": pe_dates, "series": {"pe_ttm": pe_vals, "pb": pb_vals, "channel": ch}}
    else:
        metrics.extend([
            {"key": "pe", "label": "PE 分位", "display": "—", "light": "grey"},
            {"key": "pb", "label": "PB 分位", "display": "—", "light": "grey", "hint": "该指数无 PB 数据"},
            {"key": "dividend", "label": "股息率", "display": "—", "light": "grey"},
        ])

    # 国债 + 指数点位（用于 MA120/回撤/股债比价）
    bond_err = ensure_bond_yield(db, start, end)
    idx_err = ensure_index_close(db, index_code, start, end)
    if bond_err:
        warnings.append(bond_err)
    if idx_err:
        warnings.append(idx_err)

    idx_rows = _read_index_close(db, index_code, start, end)
    ma120_light = "grey"
    dd_light = "grey"
    if idx_rows:
        from .compute.common import compute_ma, max_drawdown  # noqa: PLC0415

        ma = compute_ma([(d, Decimal(str(c))) for d, c in idx_rows], 120)
        last_date, last_close = idx_rows[-1]
        ma120_val = float(ma.get(last_date, Decimal(0)))
        if ma120_val > 0:
            dev = last_close / ma120_val
            ma120_light = light_ma120_deviation(dev)
            lights.append(ma120_light)
            metrics.append({
                "key": "ma120", "label": "MA120 偏离", "value": dev,
                "display": f"{dev:.3f}", "light": ma120_light,
                "hint": "价格/MA120，<0.985 买入区",
            })
        dd = max_drawdown([c for _, c in idx_rows])
        dd_light = light_drawdown(dd)
        lights.append(dd_light)
        metrics.append({
            "key": "drawdown", "label": "当前回撤", "value": dd,
            "display": f"{dd:.1f}%", "light": dd_light,
        })

    # 股债比价
    bond_rows = _read_bond(db, start, end)
    eb_chart, eb_light = _build_equity_bond_for_target(pe_dates, pe_vals, bond_rows, index_code, idx_rows)
    if eb_light != "grey":
        lights.append(eb_light)
    # 把股债比价灯加到 metrics（eb_chart 已含 ratio 当前值）
    current_ratio = eb_chart["series"].get("ratio", [None])
    current_ratio_val = next((v for v in reversed(current_ratio) if v is not None), None) if current_ratio else None
    metrics.append({
        "key": "equity_bond", "label": "股债比价", "value": current_ratio_val,
        "display": f"{current_ratio_val:.2f}" if current_ratio_val else "—",
        "light": eb_light,
        "hint": "EP/国债，>2 股票便宜",
    })

    layer = layer_summary(lights)
    return {
        "symbol": symbol,
        "name_cn": symbol_name,
        "resolved_index": index_code,
        "index_name": index_name,
        "as_of": idx_rows[-1][0].isoformat() if idx_rows else None,
        "metrics": metrics,
        "layer_light": layer,
        "pe_channel_chart": pe_chart_data or None,
        "equity_bond_chart": eb_chart if eb_chart.get("dates") else None,
        "warning": "; ".join(warnings) if warnings else None,
    }


def _build_equity_bond_for_target(
    pe_dates: list[str], pe_vals: list[float | None],
    bond_rows: list[tuple[date, float]],
    index_code: str, idx_rows: list[tuple[date, float]],
) -> tuple[dict, Light]:
    """为单标的算股债比价（EP/国债）+ rolling_channel + 辅助序列。返回 (chart_data, light)。

    输出序列（对齐 notebook MA5Y.ipynb 的 4 子图设计）：
    - ratio / mean / ±σ 通道（主图）
    - stock_yield（1/PE×100）、bond_yield（收益率对比图）
    - percentile（历史分位图）
    - pe_ttm（PE 图）
    - index_close（右轴指数）
    """
    if not pe_dates or not bond_rows:
        return {"dates": [], "series": {}}, "grey"
    bond_map = {d: v for d, v in bond_rows}
    idx_map = dict(idx_rows) if idx_rows else {}
    dates: list[date] = []
    ratio_vals: list[float | None] = []
    stock_yield_vals: list[float | None] = []
    bond_yield_vals: list[float | None] = []
    pe_raw_vals: list[float | None] = []
    idx_close_vals: list[float | None] = []
    for i, ds in enumerate(pe_dates):
        d = date.fromisoformat(ds)
        pe = pe_vals[i]
        y = bond_map.get(d)
        dates.append(d)
        pe_raw_vals.append(round(pe, 2) if pe else None)
        idx_close_vals.append(round(idx_map.get(d, 0), 2) if d in idx_map else None)
        if pe and y and y > 0:
            sy = round((1.0 / pe) * 100, 4)  # 盈利收益率%
            stock_yield_vals.append(sy)
            bond_yield_vals.append(round(y, 4))
            ratio_vals.append(round(sy / y, 4))
        else:
            stock_yield_vals.append(None)
            bond_yield_vals.append(None)
            ratio_vals.append(None)
    ch = rolling_channel(ratio_vals, dates, 5)
    # 历史分位（rank pct）
    valid_ratios = [v for v in ratio_vals if v is not None]
    percentile_vals: list[float | None] = []
    if valid_ratios:
        sorted_ratios = sorted(valid_ratios)
        for v in ratio_vals:
            if v is None:
                percentile_vals.append(None)
            else:
                below = sum(1 for x in sorted_ratios if x <= v)
                percentile_vals.append(round(below / len(sorted_ratios) * 100, 1))
    else:
        percentile_vals = [None] * len(dates)

    current_ratio = next((v for v in reversed(ratio_vals) if v is not None), None)
    current_mean = next((v for v in reversed(ch["mean"]) if v is not None), None)
    idx_p1 = next((v for v in reversed(ch["p1"]) if v is not None), None)
    idx_p2 = next((v for v in reversed(ch["p2"]) if v is not None), None)
    idx_n1 = next((v for v in reversed(ch["n1"]) if v is not None), None)
    idx_n2 = next((v for v in reversed(ch["n2"]) if v is not None), None)
    pos = channel_position(current_ratio, current_mean, idx_p1, idx_p2, idx_n1, idx_n2)
    light = light_equity_bond(current_ratio)
    chart = {
        "dates": [d.isoformat() for d in dates],
        "series": {
            "ratio": ratio_vals, "mean": ch["mean"],
            "p1": ch["p1"], "n1": ch["n1"],  # ±1σ 通道填充用
            "stock_yield": stock_yield_vals, "bond_yield": bond_yield_vals,
            "percentile": percentile_vals, "pe_ttm": pe_raw_vals,
            "position": pos,
            "index_close": idx_close_vals,
        },
    }
    return chart, light


# ---- 第二层：大类资产估值 ----


def build_market_signals(db: Session, lookback: str) -> dict:
    """大类资产估值信号。"""
    start, end = _resolve_window(lookback)
    metrics: list[dict] = []
    lights: list[Light] = []
    warnings: list[str] = []

    # 股债比价（沪深300）
    reg = get_registry(db, "000300")
    bond_err = ensure_bond_yield(db, start, end)
    if bond_err:
        warnings.append(bond_err)
    eb_chart: dict = {"dates": [], "series": {}}
    eb_light = "grey"
    if reg and reg.supported:
        ensure_valuation(db, "000300", reg.source_type, reg.lg_name, start, end)
        bars = read_series(db, "000300", start, end)
        pe_dates = [b.trade_date.isoformat() for b in bars]
        pe_vals = [float(b.pe_ttm) if b.pe_ttm else None for b in bars]
        bond_rows = _read_bond(db, start, end)
        idx_rows = _read_index_close(db, "000300", start, end)
        eb_chart, eb_light = _build_equity_bond_for_target(pe_dates, pe_vals, bond_rows, "000300", idx_rows)
        lights.append(eb_light)
    current_ratio = next((v for v in reversed(eb_chart["series"].get("ratio", [None])) if v is not None), None) if eb_chart["series"] else None
    metrics.append({
        "key": "equity_bond", "label": "沪深300 股债比价", "value": current_ratio,
        "display": f"{current_ratio:.2f}" if current_ratio else "—",
        "light": eb_light, "hint": "EP/国债，>2 股票便宜",
    })

    # 全收益指数 vs 5年均线（H00300 沪深300全收益）
    anchor_chart, anchor_metrics = _build_mean_anchor(db, "H00300", "沪深300全收益", start, end, 5)
    if anchor_chart.get("dates"):
        eb_chart_anchor = anchor_chart
    metrics.extend(anchor_metrics)
    lights.extend([m["light"] for m in anchor_metrics if m["light"] != "grey"])

    # 创业板/上证比值
    ratio_chart, ratio_light = _build_style_ratio(db, "399006", "000001", start, end)
    lights.append(ratio_light)
    cur_ratio = next((v for v in reversed(ratio_chart["series"].get("ratio", [None])) if v is not None), None) if ratio_chart.get("series") else None
    metrics.append({
        "key": "style_ratio", "label": "创业板/上证", "value": cur_ratio,
        "display": f"{cur_ratio:.3f}" if cur_ratio else "—", "light": ratio_light,
        "hint": "成长/价值跷跷板",
    })

    # 基金发行热度（Tushare，token 缺失降级）
    fund_light = "grey"
    fund_display = "—"
    if _has_tushare_token():
        try:
            fund_pct = _calc_fund_issue_percentile(db, end)
            fund_light = light_fund_issue(fund_pct)
            fund_display = f"{fund_pct:.0f}%分位" if fund_pct is not None else "—"
        except Exception as e:  # noqa: BLE001
            warnings.append(f"基金发行：{e}")
    else:
        warnings.append("未配置 Tushare Token，基金发行热度不可用")
    lights.append(fund_light)
    metrics.append({
        "key": "fund_issue", "label": "基金发行热度", "display": fund_display,
        "light": fund_light, "hint": "冰点=底部信号" if fund_light == "green" else None,
    })

    # 大宗商品（焦煤/沪铜/螺纹钢/BDI），近期涨跌幅信号灯 + 走势图
    commodity_chart, commodity_metrics = _build_commodity_signals(db, start, end)
    metrics.extend(commodity_metrics)
    lights.extend([m["light"] for m in commodity_metrics if m["light"] != "grey"])

    layer = layer_summary(lights)
    return {
        "as_of": eb_chart["dates"][-1] if eb_chart.get("dates") else None,
        "metrics": metrics,
        "layer_light": layer,
        "mean_anchor_chart": anchor_chart if anchor_chart.get("dates") else None,
        "equity_bond_chart": eb_chart if eb_chart.get("dates") else None,
        "ratio_chart": ratio_chart if ratio_chart.get("dates") else None,
        "commodity_chart": commodity_chart if commodity_chart.get("dates") else None,
        "warning": "; ".join(warnings) if warnings else None,
    }


def _build_mean_anchor(db: Session, index_code: str, name: str, start: date, end: date, years: int) -> tuple[dict, list[dict]]:
    """全收益指数 vs N年均线。返回 (chart, metrics)。

    均线计算需要「窗口 + 一个窗口」的数据（5年均线需从 start 前推 5 年），
    故拉取区间前推 years 年。
    """
    # 前推两个窗口确保均线有足够预热样本（5年均线需前推≥5年数据）
    fetch_start = start - timedelta(days=years * 365 * 2 + 60)
    ensure_index_close(db, index_code, fetch_start, end, total_return=True)
    all_rows = _read_index_close(db, index_code, fetch_start, end)
    if not all_rows:
        return {}, [{"key": f"anchor_{index_code}", "label": f"{name} 偏离", "display": "—", "light": "grey"}]
    from .compute.common import compute_ma  # noqa: PLC0415

    ma_period = int(years * 250)  # ≈ 年交易日数
    ma = compute_ma([(d, Decimal(str(c))) for d, c in all_rows], ma_period)
    ma60 = compute_ma([(d, Decimal(str(c))) for d, c in all_rows], 60)  # 60 日均线（找卖点）
    # 只展示 [start, end] 区间（均线用 all_rows 全量算，保证预热充分）
    rows = [(d, c) for d, c in all_rows if d >= start]
    dates: list[str] = []
    close_vals: list[float | None] = []
    ma_vals: list[float | None] = []
    ma60_vals: list[float | None] = []
    upper_vals: list[float | None] = []  # MA+15%
    lower_vals: list[float | None] = []  # MA-15%
    sell_vals: list[float | None] = []  # MA+28% 卖出线
    dev_vals: list[float | None] = []
    last_dev: float | None = None
    for d, c in rows:
        dates.append(d.isoformat())
        close_vals.append(round(c, 2))
        m = ma.get(d)
        m60 = ma60.get(d)
        ma60_vals.append(round(float(m60), 2) if m60 else None)
        if m and float(m) > 0:
            mf = float(m)
            ma_vals.append(round(mf, 2))
            upper_vals.append(round(mf * 1.15, 2))
            lower_vals.append(round(mf * 0.85, 2))
            sell_vals.append(round(mf * 1.28, 2))
            dev = round((c - mf) / mf * 100, 2)
            dev_vals.append(dev)
            last_dev = dev
        else:
            ma_vals.append(None)
            upper_vals.append(None)
            lower_vals.append(None)
            sell_vals.append(None)
            dev_vals.append(None)
    light = light_mean_anchor(last_dev)
    chart = {
        "dates": dates,
        "series": {
            "close": close_vals, "ma": ma_vals, "ma60": ma60_vals,
            "upper": upper_vals, "lower": lower_vals, "sell_line": sell_vals,
            "deviation": dev_vals,
        },
    }
    metric = [{
        "key": f"anchor_{index_code}", "label": f"{name} 偏离",
        "value": last_dev, "display": f"{last_dev:+.1f}%" if last_dev is not None else "—",
        "light": light, "hint": "vs 5年均线，<-10% 低估",
    }]
    return chart, metric


def _build_style_ratio(db: Session, code_a: str, code_b: str, start: date, end: date) -> tuple[dict, Light]:
    """两指数比值（创业板/上证）。返回 (chart, light)。比值无信号灯（grey），仅展示。"""
    ensure_index_close(db, code_a, start, end)
    ensure_index_close(db, code_b, start, end)
    rows_a = dict(_read_index_close(db, code_a, start, end))
    rows_b = dict(_read_index_close(db, code_b, start, end))
    common = sorted(set(rows_a.keys()) & set(rows_b.keys()))
    if not common:
        return {"dates": [], "series": {}}, "grey"
    dates = [d.isoformat() for d in common]
    ratio = [round(rows_a[d] / rows_b[d], 4) if rows_b[d] else None for d in common]
    return {"dates": dates, "series": {"ratio": ratio}}, "grey"


# 大宗商品名称映射
_COMMODITY_NAMES = {"JM0": "焦煤", "CU0": "沪铜", "RB0": "螺纹钢", "BDI": "BDI运价指数"}


def _build_commodity_signals(db: Session, start: date, end: date) -> tuple[dict, list[dict]]:
    """大宗商品走势图 + 近 20 日涨跌幅信号灯。返回 (chart, metrics)。"""
    from .compute.signal_light import light_commodity  # noqa: PLC0415

    all_series: dict[str, list[float | None]] = {}
    all_dates: set[date] = set()
    metrics: list[dict] = []

    for sym in ["JM0", "CU0", "RB0", "BDI"]:
        err = ensure_commodity(db, sym, start, end)
        if err:
            metrics.append({
                "key": f"commodity_{sym}", "label": f"{_COMMODITY_NAMES[sym]} 20日涨跌",
                "display": "—", "light": "grey", "hint": err[:40],
            })
            continue
        rows = _read_commodity(db, sym, start, end)
        if not rows:
            metrics.append({
                "key": f"commodity_{sym}", "label": f"{_COMMODITY_NAMES[sym]} 20日涨跌",
                "display": "—", "light": "grey",
            })
            continue
        d_map = {d: v for d, v in rows}
        all_dates |= set(d_map.keys())
        all_series[sym] = [None] * 0  # placeholder, 后面按 sorted dates 填充
        # 算近 20 日涨跌幅
        recent = rows[-20:]
        if len(recent) >= 2:
            pct = round((recent[-1][1] - recent[0][1]) / recent[0][1] * 100, 1)
        else:
            pct = None
        light = light_commodity(pct)
        metrics.append({
            "key": f"commodity_{sym}", "label": f"{_COMMODITY_NAMES[sym]} 20日涨跌",
            "value": pct, "display": f"{pct:+.1f}%" if pct is not None else "—",
            "light": light,
            "hint": f"现价 {recent[-1][1]:.1f}" if recent else None,
        })

    # 组装 chart：按日期对齐，缺失为 None
    sorted_dates = sorted(all_dates)
    chart = {"dates": [], "series": {}}
    for sym in ["JM0", "CU0", "RB0", "BDI"]:
        rows = _read_commodity(db, sym, start, end)
        d_map = {d: v for d, v in rows}
        # 归一化（各品种量级差异大，归一到首日=100 便于同图对比）
        first_val = next((v for v in d_map.values() if v), None)
        if first_val:
            chart["series"][sym] = [
                round(d_map.get(d, 0) / first_val * 100, 2) if d in d_map else None
                for d in sorted_dates
            ]
        else:
            chart["series"][sym] = [None] * len(sorted_dates)
    chart["dates"] = [d.isoformat() for d in sorted_dates]
    return chart, metrics


def _calc_fund_issue_percentile(db: Session, end: date) -> float | None:
    """基金发行规模当月 vs 近 3 年历史分位。

    ensure 落库（fund_issue indicator，月频）后读本地算分位，避免每次拉 fund_basic 全量。
    """
    from .fetcher.macro_fetcher import fetch_fund_issue  # noqa: PLC0415

    start = end - timedelta(days=365 * 3 + 60)
    # ensure：raw_macro_indicator 中 fund_issue 缺口补齐（月频容差 35 天）
    _ensure_macro(db, "fund_issue", start, end, fetch_fn=fetch_fund_issue)
    series = _read_macro(db, "fund_issue", start, end)
    if not series:
        return None
    cur_val = series[-1][1]
    vals = sorted(v for _, v in series if v > 0)
    if not vals:
        return None
    below = sum(1 for v in vals if v <= cur_val)
    return round(below / len(vals) * 100, 1)


# ---- 第三层：资金 + 宏观 ----


def build_capital_macro_signals(db: Session, symbol: str, lookback: str) -> dict:
    """资金 + 宏观信号（全 Tushare，token 缺失全降级）。symbol 用于 ETF 份额变动。"""
    start, end = _resolve_window(lookback)
    metrics: list[dict] = []
    lights: list[Light] = []
    warnings: list[str] = []

    if not _has_tushare_token():
        return {
            "as_of": None, "metrics": [], "layer_light": "grey",
            "warning": "未配置 Tushare Token，第三层（资金/宏观）不可用。请在右上角钥匙图标中配置。",
        }

    # 宏观四件套
    macro_specs = [
        ("pmi", "PMI", "制造业 PMI，>50 扩张"),
        ("m1m2_gap", "M1/M2 剪刀差", "M1 同比 - M2 同比，收窄=回暖"),
        ("sf_yoy", "社融增速", "存量同比，>0 放量"),
        ("ppi_yoy", "PPI", "当月同比，>0 上行利好周期"),
    ]
    # m1m2_gap 需特殊处理（两指标做差）
    for indicator, label, hint in macro_specs:
        try:
            if indicator == "m1m2_gap":
                _ensure_macro(db, "m1_yoy", start, end)
                _ensure_macro(db, "m2_yoy", start, end)
                m1 = _read_macro(db, "m1_yoy", start, end)
                m2 = _read_macro(db, "m2_yoy", start, end)
                m2_map = dict(m2)
                gap_series = [(d, v - m2_map.get(d, 0)) for d, v in m1 if d in m2_map]
                val = gap_series[-1][1] if gap_series else None
            else:
                _ensure_macro(db, indicator, start, end)
                series = _read_macro(db, indicator, start, end)
                val = series[-1][1] if series else None
            light = light_macro(indicator, val)
            lights.append(light)
            metrics.append({
                "key": indicator, "label": label, "value": val,
                "display": f"{val:.1f}" if val is not None else "—",
                "light": light, "hint": hint,
            })
        except Exception as e:  # noqa: BLE001
            warnings.append(f"{label}：{e}")
            metrics.append({"key": indicator, "label": label, "display": "—", "light": "grey", "hint": hint})

    # 融资余额（历史分位）
    try:
        _ensure_margin(db, start, end)
        margin = _read_margin(db, start, end)
        if margin:
            rzye_series = [r[1] for r in margin]
            cur_rzye = rzye_series[-1]
            pct = percentile_rank(cur_rzye, rzye_series)
            light = light_margin_percentile(pct)
            lights.append(light)
            metrics.append({
                "key": "margin", "label": "融资余额分位", "value": pct,
                "display": f"{pct:.0f}%", "light": light,
                "hint": "<20% 杠杆清洗=底部" if light == "green" else ">80% 过热=顶部" if light == "red" else None,
            })
            # 融券余额分位（空头集中度；极高可能是见底信号，但阈值与融资相反不直观，暂同口径）
            rqye_series = [r[2] for r in margin]
            cur_rqye = rqye_series[-1]
            rqye_pct = percentile_rank(cur_rqye, rqye_series)
            rqye_light = light_margin_percentile(rqye_pct)
            lights.append(rqye_light)
            metrics.append({
                "key": "rqye", "label": "融券余额分位", "value": rqye_pct,
                "display": f"{rqye_pct:.0f}%", "light": rqye_light,
                "hint": "空头集中度，极高可能是见底信号",
            })
    except Exception as e:  # noqa: BLE001
        warnings.append(f"融资融券：{e}")
        metrics.append({"key": "margin", "label": "融资余额", "display": "—", "light": "grey"})
        metrics.append({"key": "rqye", "label": "融券余额", "display": "—", "light": "grey"})

    # 北向资金（ensure 落库 raw_macro_indicator，避免每次实时调 Tushare）
    northbound_chart: dict = {"dates": [], "series": {}}
    try:
        _ensure_macro(db, "north_money", start, end, fetch_fn=fetch_northbound)
        nb_series = _read_macro(db, "north_money", start, end)
        if nb_series:
            nb_val = nb_series[-1][1]  # 万元
            lights.append("grey")  # 北向无固定阈值，仅展示
            metrics.append({
                "key": "northbound", "label": "北向资金", "value": nb_val,
                "display": f"{nb_val / 10000:.2f}亿", "light": "grey", "hint": "外资态度（2024后总额披露）",
            })
            northbound_chart = {
                "dates": [d.isoformat() for d, _ in nb_series],
                "series": {"north_money": [round(v / 1e4, 2) for _, v in nb_series]},  # 万元→亿元
            }
    except Exception as e:  # noqa: BLE001
        warnings.append(f"北向：{e}")

    # ETF 份额变动（复用 028 ensure_etf_shares 落库；按标的查询）
    etf_share_chart: dict = {"dates": [], "series": {}}
    try:
        from .etf_share_data import ensure_etf_shares  # noqa: PLC0415

        etf_sym = symbol if symbol.startswith("5") else "510300"
        err = ensure_etf_shares(db, etf_sym, start, end)
        if err:
            warnings.append(f"ETF份额：{err}")
        else:
            from ..models.etf_share import RawEtfShareDaily  # noqa: PLC0415

            rows = db.execute(
                select(RawEtfShareDaily.trade_date, RawEtfShareDaily.fd_share)
                .where(
                    RawEtfShareDaily.symbol == etf_sym,
                    RawEtfShareDaily.trade_date >= start,
                    RawEtfShareDaily.trade_date <= end,
                )
                .order_by(RawEtfShareDaily.trade_date)
            ).all()
            if len(rows) >= 2:
                shares = [float(r.fd_share) for r in rows]
                dates_list = [r.trade_date for r in rows]
                # 环比变动（万份）
                changes = [0.0] + [round(shares[i] - shares[i - 1], 2) for i in range(1, len(shares))]
                recent_change = changes[-1]
                # 近 20 日累计变动
                recent_20 = sum(changes[-20:]) if len(changes) >= 20 else sum(changes)
                light = "green" if recent_20 > 0 else "red" if recent_20 < 0 else "yellow"
                lights.append(light)
                metrics.append({
                    "key": "etf_share", "label": "ETF份额变动", "value": recent_change,
                    "display": f"{recent_change / 1e4:+.2f}亿份" if recent_change else "—",
                    "light": light,
                    "hint": f"近20日累计 {recent_20 / 1e4:+.1f}亿份",
                })
                etf_share_chart = {
                    "dates": [d.isoformat() for d in dates_list],
                    "series": {"change": changes},
                }
    except Exception as e:  # noqa: BLE001
        warnings.append(f"ETF份额：{e}")

    layer = layer_summary(lights)

    # ---- 图 1：宏观四指标月度序列（PMI / M1 / M2 / 社融 / PPI）----
    macro_chart: dict = {"dates": [], "series": {}}
    try:
        pmi_s = dict(_read_macro(db, "pmi", start, end))
        m1_s = dict(_read_macro(db, "m1_yoy", start, end))
        m2_s = dict(_read_macro(db, "m2_yoy", start, end))
        sf_s = dict(_read_macro(db, "sf_yoy", start, end))
        ppi_s = dict(_read_macro(db, "ppi_yoy", start, end))
        months = sorted(set(pmi_s) | set(m1_s) | set(m2_s) | set(sf_s) | set(ppi_s))
        macro_chart = {
            "dates": [d.isoformat() for d in months],
            "series": {
                "pmi": [pmi_s.get(d) for d in months],
                "m1_yoy": [m1_s.get(d) for d in months],
                "m2_yoy": [m2_s.get(d) for d in months],
                "sf_yoy": [sf_s.get(d) for d in months],
                "ppi_yoy": [ppi_s.get(d) for d in months],
            },
        }
    except Exception:  # noqa: BLE001
        pass

    # ---- 图 2：融资余额 vs 沪深300 ----
    margin_chart: dict = {"dates": [], "series": {}}
    try:
        margin_rows = _read_margin(db, start, end)
        if margin_rows:
            idx_rows = _read_index_close(db, "000300", start, end)
            idx_map = dict(idx_rows)
            margin_chart = {
                "dates": [r[0].isoformat() for r in margin_rows],
                "series": {
                    "rzye": [round(r[1] / 1e8, 2) for r in margin_rows],  # 融资余额 元→亿元
                    "rqye": [round(r[2] / 1e8, 2) for r in margin_rows],  # 融券余额 元→亿元
                    "hs300": [idx_map.get(r[0]) for r in margin_rows],
                },
            }
    except Exception:  # noqa: BLE001
        pass

    return {
        "as_of": end.isoformat(),
        "metrics": metrics,
        "layer_light": layer,
        "macro_chart": macro_chart if macro_chart["dates"] else None,
        "margin_chart": margin_chart if margin_chart["dates"] else None,
        "etf_share_chart": etf_share_chart if etf_share_chart.get("dates") else None,
        "northbound_chart": northbound_chart if northbound_chart.get("dates") else None,
        "warning": "; ".join(warnings) if warnings else None,
    }


# ---- 共振汇总 ----


def build_resonance(db: Session, symbol: str, lookback: str) -> dict:
    """三层共振汇总。三层 build 并行执行（各自独立 session，互无依赖）。"""
    from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

    from ..database import SessionLocal  # noqa: PLC0415

    def _run(builder):
        """在独立 session 中执行 build 函数，确保线程安全。"""
        with SessionLocal() as sdb:
            return builder(sdb)

    with ThreadPoolExecutor(max_workers=3) as pool:
        ft = pool.submit(_run, lambda d: build_target_signals(d, symbol, lookback))
        fm = pool.submit(_run, lambda d: build_market_signals(d, lookback))
        fc = pool.submit(_run, lambda d: build_capital_macro_signals(d, symbol, lookback))
        t = ft.result()
        m = fm.result()
        c = fc.result()

    status, advice = resonance_fn(t["layer_light"], m["layer_light"], c["layer_light"])
    return {
        "layer1": t["layer_light"],
        "layer2": m["layer_light"],
        "layer3": c["layer_light"],
        "overall_status": status,
        "action_advice": advice,
        "as_of": t.get("as_of") or m.get("as_of") or c.get("as_of"),
        # 顺带返回三层明细，前端一次拿全（避免并发 4 请求）
        "target": t,
        "market": m,
        "macro": c,
    }
