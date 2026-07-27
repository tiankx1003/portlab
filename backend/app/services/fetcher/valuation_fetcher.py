"""指数估值数据拉取（024）：lg（乐咕乐股）+ csindex（中证指数公司）双源。

不走 ``DataFetcher`` 抽象基类（与 016 MVP 一致——估值直接 ``import akshare``），
``_FETCHERS`` 注册表不变。异常统一抛 ``FetchError``（中文友好）。
csindex 静态 xls 接口偶发不稳定，加重试（2 次，间隔 1s）。

数据源列映射（akshare 1.18.64 实测）：
- ``stock_index_pe_lg``：``滚动市盈率`` → pe_ttm；``stock_index_pb_lg``：``市净率`` → pb。
- ``stock_zh_index_hist_csindex``：``滚动市盈率`` → pe_ttm（过滤 NaN 行）。
- ``stock_zh_index_value_csindex``：``股息率1`` → dividend_yield（当日快照）。
"""

import logging
import time
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from .base import FetchError

logger = logging.getLogger(__name__)

# csindex 重试（静态接口偶发不稳定）
_CSINDEX_RETRIES = 2
_CSINDEX_BACKOFF = 1.0  # 秒


@dataclass(frozen=True)
class ValuationBar:
    """指数估值单日数据（字段对齐 ``raw_index_valuation_daily`` 表列）。"""

    index_code: str
    trade_date: date
    pe_ttm: Decimal | None
    pb: Decimal | None
    dividend_yield: Decimal | None
    source: str  # lg / csindex


def _to_dec(v) -> Decimal | None:
    """宽松转 Decimal：None / NaN / 非数 → None。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    try:
        if pd.isna(f):
            return None
    except (TypeError, ValueError):
        pass
    return Decimal(str(f))


def fetch_lg(index_code: str, lg_name: str) -> list[ValuationBar]:
    """lg 源：PE(``stock_index_pe_lg``) + PB(``stock_index_pb_lg``) 按日期对齐合并。

    lg 接口参数为中文指数名（lg_name），返回全部历史（无日期参数）。
    """
    try:
        import akshare as ak  # noqa: PLC0415

        df_pe = ak.stock_index_pe_lg(symbol=lg_name)
        df_pb = ak.stock_index_pb_lg(symbol=lg_name)
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"lg 估值接口异常（{lg_name}）：{e}") from e

    if df_pe is None or df_pe.empty or "滚动市盈率" not in df_pe.columns:
        return []

    date_col = "日期"
    pe_series = pd.to_datetime(df_pe[date_col])
    pe_map = dict(zip(pe_series, df_pe["滚动市盈率"], strict=False))

    pb_map: dict = {}
    if df_pb is not None and not df_pb.empty and "市净率" in df_pb.columns:
        pb_series = pd.to_datetime(df_pb[date_col])
        pb_map = dict(zip(pb_series, df_pb["市净率"], strict=False))

    bars: list[ValuationBar] = []
    for d in sorted(pe_map):
        bars.append(
            ValuationBar(
                index_code=index_code,
                trade_date=d.date(),
                pe_ttm=_to_dec(pe_map[d]),
                pb=_to_dec(pb_map.get(d)),
                dividend_yield=None,
                source="lg",
            )
        )
    return bars


def fetch_csindex(index_code: str, start: date, end: date) -> list[ValuationBar]:
    """csindex 源：PE 历史（``stock_zh_index_hist_csindex``，过滤 NaN）+ 当日股息率快照。"""
    df = _csindex_with_retry(
        lambda: _safe_hist(index_code, start, end),
        label=f"csindex 历史（{index_code}）",
    )
    if df is None or df.empty or "滚动市盈率" not in df.columns:
        return []

    date_col = "日期"
    df = df[[date_col, "滚动市盈率"]].copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    # 股息率快照：{date: value}
    div_map = fetch_csindex_dividend(index_code)

    bars: list[ValuationBar] = []
    for _, row in df.iterrows():
        pe = _to_dec(row["滚动市盈率"])
        if pe is None:
            continue  # 过滤 NaN PE 行
        d = row[date_col].date()
        bars.append(
            ValuationBar(
                index_code=index_code,
                trade_date=d,
                pe_ttm=pe,
                pb=None,
                dividend_yield=_to_dec(div_map.get(d)),
                source="csindex",
            )
        )

    # 快照日若 hist 缺该日，仍补一条 dividend_yield 记录（pe 留空）
    for d, div in div_map.items():
        if div is None:
            continue
        if not any(b.trade_date == d for b in bars):
            bars.append(ValuationBar(index_code, d, None, None, _to_dec(div), "csindex"))
    bars.sort(key=lambda b: b.trade_date)
    return bars


def _safe_hist(index_code: str, start: date, end: date):
    import akshare as ak  # noqa: PLC0415

    return ak.stock_zh_index_hist_csindex(
        symbol=index_code,
        start_date=start.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    )


def fetch_csindex_dividend(index_code: str) -> dict:
    """股息率快照：``stock_zh_index_value_csindex`` 全量 → {date: 股息率1}。

    失败不抛异常（股息率为可选指标），返回空 dict。
    """
    def _call():
        import akshare as ak  # noqa: PLC0415

        return ak.stock_zh_index_value_csindex(symbol=index_code)

    df = _csindex_with_retry(_call, label=f"csindex 股息率（{index_code}）", swallow=True)
    if df is None or df.empty or "股息率1" not in df.columns or "日期" not in df.columns:
        return {}
    df = df[["日期", "股息率1"]].copy()
    df["日期"] = pd.to_datetime(df["日期"])
    return {d.date(): v for d, v in zip(df["日期"], df["股息率1"], strict=False)}


def _csindex_with_retry(call, label: str, swallow: bool = False):
    """csindex 接口重试包装。swallow=True 时最终失败返回 None 而非抛异常。"""
    last_err: Exception | None = None
    for attempt in range(_CSINDEX_RETRIES + 1):
        try:
            return call()
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < _CSINDEX_RETRIES:
                time.sleep(_CSINDEX_BACKOFF)
    if swallow:
        logger.warning("%s 重试 %d 次仍失败：%s", label, _CSINDEX_RETRIES, last_err)
        return None
    raise FetchError(f"{label} 异常：{last_err}")


def fetch_valuation(
    index_code: str,
    source_type: str,
    lg_name: str | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[ValuationBar]:
    """按 source_type 分发到 lg / csindex 拉取。"""
    if source_type == "lg":
        if not lg_name:
            raise FetchError(f"lg 源缺少中文指数名（{index_code}）")
        return fetch_lg(index_code, lg_name)
    if source_type == "csindex":
        today = date.today()
        return fetch_csindex(index_code, start or today, end or today)
    raise FetchError(f"不支持的数据源（{index_code}: {source_type}）")
