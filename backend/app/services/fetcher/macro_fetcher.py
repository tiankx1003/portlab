"""估值与信号看板数据拉取 — Tushare 部分（032）：宏观指标 + 融资融券 + 基金发行。

与 017 etf_flow 同模式：直接 ``_resolve_token()`` + ``ts.pro_api()``，不走 ``resolve_source`` 开关，
只校验 token 存在。token 缺失时抛 ``FetchError``（调用方据此降级）。

积分不足（命中 ``_PERMISSION_KEYWORDS``）透传 Tushare 原始 msg。复用 013 的 ``_throttle`` 节流。

数据源（Tushare Pro 官方文档）：
- ``sf_month`` (doc_id=310, 2000分)：社融，``stk_endval`` 存量→算同比。
- ``cn_m`` (doc_id=242, 600分)：货币供应量，``m1_yoy``/``m2_yoy``。
- ``cn_ppi`` (doc_id=245, 600分)：PPI，``ppi_yoy`` 当月同比。
- ``cn_pmi`` (doc_id=325, 5000分)：PMI，``制造业PMI``。
- ``margin`` (doc_id=58, 2000分)：融资融券，``rzye``/``rqye``。
- ``fund_basic`` (doc_id=25, 120分)：基金基础信息，``issue_size`` 发行规模。
"""

import logging
from dataclasses import dataclass
from datetime import date

from .base import FetchError
from .tushare_fetcher import _PERMISSION_KEYWORDS, _resolve_token, _throttle

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MacroBar:
    """宏观指标单日/单月（字段对齐 ``raw_macro_indicator`` 表列）。"""

    indicator: str
    ref_date: date
    value: float | None
    source: str


def _get_pro():
    """解析 token 并返回 Tushare pro 客户端。token 缺失抛 FetchError。"""
    token = _resolve_token()  # token 缺失时抛 FetchError（中文友好）
    import tushare as ts  # noqa: PLC0415

    ts.set_token(token)
    return ts.pro_api()


def _check_permission(e: Exception, label: str) -> None:
    """积分/权限不足时透传原始 msg，其余异常也抛 FetchError。"""
    msg = str(e)
    if any(k in msg for k in _PERMISSION_KEYWORDS):
        raise FetchError(f"{label}：{msg}") from e
    raise FetchError(f"{label}异常：{e}") from e


def fetch_macro(indicator: str, start: date, end: date) -> list[MacroBar]:
    """拉取 [start, end] 区间宏观指标。按 indicator 分发到 Tushare 接口。

    indicator ∈ {sf_yoy, m1_yoy, m2_yoy, ppi_yoy, pmi}。
    月频指标 ref_date 取月初（YYYY-MM-01）。
    """
    try:
        pro = _get_pro()
    except FetchError:
        raise

    sd = start.strftime("%Y%m%d")
    ed = end.strftime("%Y%m%d")
    bars: list[MacroBar] = []

    try:
        if indicator == "sf_yoy":
            _throttle()
            df = pro.sf_month(start_m=sd[:6], end_m=ed[:6])
            if df is None or df.empty or "stk_endval" not in df.columns:
                return []
            df = df.sort_values("month")
            prev: float | None = None
            for _, row in df.iterrows():
                v = _to_float(row["stk_endval"])
                yoy = None
                if v is not None and prev is not None and prev != 0:
                    yoy = round((v - prev) / prev * 100, 2)
                prev = v if v is not None else prev
                if yoy is not None:
                    bars.append(MacroBar("sf_yoy", _month_to_date(row["month"]), yoy, "tushare"))
        elif indicator in ("m1_yoy", "m2_yoy"):
            _throttle()
            df = pro.cn_m(start_m=sd[:6], end_m=ed[:6])
            if df is None or df.empty:
                return []
            col = "m1_yoy" if indicator == "m1_yoy" else "m2_yoy"
            if col not in df.columns:
                return []
            df = df.sort_values("month")
            for _, row in df.iterrows():
                v = _to_float(row[col])
                if v is not None:
                    bars.append(MacroBar(indicator, _month_to_date(row["month"]), v, "tushare"))
        elif indicator == "ppi_yoy":
            _throttle()
            df = pro.cn_ppi(start_m=sd[:6], end_m=ed[:6])
            if df is None or df.empty or "ppi_yoy" not in df.columns:
                return []
            df = df.sort_values("month")
            for _, row in df.iterrows():
                v = _to_float(row["ppi_yoy"])
                if v is not None:
                    bars.append(MacroBar("ppi_yoy", _month_to_date(row["month"]), v, "tushare"))
        elif indicator == "pmi":
            _throttle()
            df = pro.cn_pmi(start_m=sd[:6], end_m=ed[:6])
            if df is not None and not df.empty:
                df.columns = [c.lower() for c in df.columns]  # cn_pmi 列名全大写，统一转小写
            if df is None or df.empty or "pmi010000" not in df.columns:
                return []
            df = df.sort_values("month")
            for _, row in df.iterrows():
                v = _to_float(row["pmi010000"])
                if v is not None:
                    bars.append(MacroBar("pmi", _month_to_date(row["month"]), v, "tushare"))
        else:
            raise FetchError(f"未知宏观指标：{indicator}")
    except FetchError:
        raise
    except Exception as e:  # noqa: BLE001
        _check_permission(e, f"宏观指标({indicator})")
    return bars


def fetch_margin(start: date, end: date) -> list[dict]:
    """拉取 [start, end] 区间融资融券余额（交易所级汇总，按 trade_date 去重留最新）。

    返回 list[dict]：{trade_date, rzye, rqye}。
    """
    try:
        pro = _get_pro()
    except FetchError:
        raise

    sd = start.strftime("%Y%m%d")
    ed = end.strftime("%Y%m%d")
    try:
        _throttle()
        df = pro.margin(start_date=sd, end_date=ed)
    except Exception as e:  # noqa: BLE001
        _check_permission(e, "融资融券")
    if df is None or df.empty or "trade_date" not in df.columns:
        return []
    # 按 trade_date 聚合（多交易所取和），去重留最新
    df = df.groupby("trade_date", as_index=False).agg({"rzye": "sum", "rqye": "sum"})
    df = df.sort_values("trade_date")
    rows: list[dict] = []
    for _, row in df.iterrows():
        rows.append(
            {
                "trade_date": _yyyymmdd_to_date(row["trade_date"]),
                "rzye": _to_float(row.get("rzye")),
                "rqye": _to_float(row.get("rqye")),
                "source": "tushare",
            }
        )
    return rows


def fetch_fund_issue(months: list[str]) -> dict[str, float]:
    """按月聚合基金发行规模（股基 + 偏股混合）。

    months: ["202601", "202602", ...]（YYYYMM）。
    返回 {month: issue_size_亿元}。需 120 积分（fund_basic 低门槛）。
    """
    try:
        pro = _get_pro()
    except FetchError:
        raise

    result: dict[str, float] = {m: 0.0 for m in months}
    try:
        _throttle()
        # fund_basic：market="O"（场外）覆盖最全；若无 issue_size 列则回退全量
        df = pro.fund_basic(market="O")
        if df is None or df.empty or "found_date" not in df.columns or "issue_size" not in df.columns:
            _throttle()
            df = pro.fund_basic()
        if df is None or df.empty or "found_date" not in df.columns or "issue_size" not in df.columns:
            return result
        # 筛股基/偏股混合
        if "fund_type" in df.columns:
            df = df[df["fund_type"].isin(["股票型", "偏股混合型"])]
        if df.empty:
            return result
        # found_date → YYYYMM，按月聚合 issue_size
        df = df.dropna(subset=["found_date", "issue_size"])
        if df.empty:
            return result
        df = df.copy()
        df["month"] = df["found_date"].astype(str).str[:6]
        df["issue_size"] = df["issue_size"].astype(float)
        monthly = df.groupby("month")["issue_size"].sum()
        for m in months:
            if m in monthly.index:
                result[m] = round(float(monthly[m]), 2)
    except Exception as e:  # noqa: BLE001
        _check_permission(e, "基金发行规模")
    return result


# ---- 工具 ----


def _to_float(v) -> float | None:
    """宽松转 float：None / NaN / 非数 → None。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN 判断


def _month_to_date(yyyymm: str) -> date:
    """'202601' / '2026-01' → date(2026, 1, 1)。"""
    s = str(yyyymm).replace("-", "")[:6]
    return date(int(s[:4]), int(s[4:6]), 1)


def _yyyymmdd_to_date(yyyymmdd: str) -> date:
    """'20260804' → date(2026, 8, 4)。"""
    s = str(yyyymmdd).replace("-", "")[:8]
    return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
