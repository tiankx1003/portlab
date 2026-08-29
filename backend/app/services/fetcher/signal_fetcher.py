"""估值与信号看板数据拉取 — AkShare 部分（032）：十年期国债 + 指数日线点位。

不走 ``DataFetcher`` 抽象基类（与 024 估值 fetcher 一致——直接 ``import akshare``）。
异常统一抛 ``FetchError``（中文友好）。宽松 Decimal 转换复用 ``valuation_fetcher._to_dec``。

数据源列映射（akshare 1.18.64 实测）：
- ``bond_zh_us_rate``：``日期``(datetime.date) + ``中国国债收益率10年``(float, %)。
  一次调用返回全历史（1990 起），start_date 控制起点。
- ``stock_zh_index_daily``：``date`` + ``close``，参数需 ``sh``/``sz`` 前缀（价格指数）。
- ``stock_zh_index_hist_csindex``：``日期`` + ``收盘``，参数为 H 全收益代码（须显式传日期）。
"""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from .base import FetchError
from .valuation_fetcher import _to_dec

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BondBar:
    """十年期国债收益率单日（字段对齐 ``raw_bond_yield_daily`` 表列）。"""

    trade_date: date
    yield_10y: Decimal | None
    source: str


@dataclass(frozen=True)
class IndexBar:
    """指数日线单日（字段对齐 ``raw_index_daily`` 表列）。"""

    index_code: str
    trade_date: date
    close: Decimal | None
    index_type: str  # price / total_return
    source: str


# ---- 十年期国债收益率 ----


def fetch_bond_yield(start: date, end: date) -> list[BondBar]:
    """拉取 [start, end] 区间十年期国债收益率。

    主源 ``bond_zh_us_rate``（一次调用全历史，按区间过滤）；
    失败回退 ``bond_china_yield``（中债国债收益率曲线，按区间分段）。
    """
    bars = _fetch_bond_zh_us_rate(start, end)
    if bars:
        return bars
    logger.warning("bond_zh_us_rate 无数据，回退 bond_china_yield")
    return _fetch_bond_china_yield(start, end)


def _fetch_bond_zh_us_rate(start: date, end: date) -> list[BondBar]:
    """主源：中美国债收益率，取「中国国债收益率10年」列。"""
    try:
        import akshare as ak  # noqa: PLC0415

        df = ak.bond_zh_us_rate(start_date=start.strftime("%Y%m%d"))
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"bond_zh_us_rate 接口异常：{e}") from e

    if df is None or df.empty or "中国国债收益率10年" not in df.columns:
        return []

    df = df[["日期", "中国国债收益率10年"]].copy()
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期")
    bars: list[BondBar] = []
    for _, row in df.iterrows():
        d = row["日期"].date()
        if d < start or d > end:
            continue
        y = _to_dec(row["中国国债收益率10年"])
        if y is None:
            continue  # 过滤 NaN
        bars.append(BondBar(trade_date=d, yield_10y=y, source="bond_zh_us_rate"))
    return bars


def _fetch_bond_china_yield(start: date, end: date) -> list[BondBar]:
    """回退源：中债国债收益率曲线，取「10年」列（过滤「中债国债收益率曲线」）。"""
    try:
        import akshare as ak  # noqa: PLC0415

        df = ak.bond_china_yield(
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d")
        )
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"bond_china_yield 接口异常：{e}") from e

    if df is None or df.empty:
        return []
    if "曲线名称" in df.columns:
        df = df[df["曲线名称"] == "中债国债收益率曲线"]
    if df.empty or "10年" not in df.columns or "日期" not in df.columns:
        return []

    df = df[["日期", "10年"]].copy()
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期")
    bars: list[BondBar] = []
    for _, row in df.iterrows():
        y = _to_dec(row["10年"])
        if y is None:
            continue
        bars.append(BondBar(trade_date=row["日期"].date(), yield_10y=y, source="bond_china_yield"))
    return bars


# ---- 指数日线点位 ----


def _to_prefixed_symbol(index_code: str) -> str:
    """裸代码 → ``stock_zh_index_daily`` 所需的 sh/sz 前缀。

    深交所指数（399xxx 深证系列）以 3 开头 → sz；其余（000xxx 上证系列）→ sh。
    """
    if index_code.startswith("3"):
        return f"sz{index_code}"
    return f"sh{index_code}"


def _parse_csindex_df(
    df: pd.DataFrame, index_code: str, start: date, end: date, index_type: str, source: str,
) -> list[IndexBar]:
    """解析 ``stock_zh_index_hist_csindex`` 返回（列名「日期」「收盘」），按区间过滤为 IndexBar。

    ``index_type`` 取 ``price`` / ``total_return``，``source`` 取 ``akshare_csindex``。
    供价格指数（回退源）与全收益指数共用，消除列名解析重复。
    """
    if df is None or df.empty or "日期" not in df.columns or "收盘" not in df.columns:
        return []

    df = df[["日期", "收盘"]].copy()
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期")
    bars: list[IndexBar] = []
    for _, row in df.iterrows():
        d = row["日期"].date()
        if d < start or d > end:
            continue
        bars.append(
            IndexBar(
                index_code=index_code,
                trade_date=d,
                close=_to_dec(row["收盘"]),
                index_type=index_type,
                source=source,
            )
        )
    return bars


def _fetch_index_close_csindex(index_code: str, start: date, end: date) -> list[IndexBar]:
    """回退源：中证指数公司 ``stock_zh_index_hist_csindex``（对 930xxx 等中证代码通用）。

    ⚠️ 必须显式传 start_date/end_date，否则该接口默认 end_date=20240604 会误判为数据过期。
    """
    try:
        import akshare as ak  # noqa: PLC0415

        df = ak.stock_zh_index_hist_csindex(
            symbol=index_code,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"指数行情接口异常（csindex 回退 {index_code}）：{e}") from e

    return _parse_csindex_df(df, index_code, start, end, "price", "akshare_csindex")


def fetch_index_close(index_code: str, start: date, end: date) -> list[IndexBar]:
    """拉取 [start, end] 区间价格指数收盘点位。

    主源 ``stock_zh_index_daily``（交易所日线，覆盖 sh/sz 前缀的交易所指数）。
    中证指数公司发布的代码（如 930955 红利低波100）交易所日线不收录，返回空 df 且
    akshare 内部会抛 ``KeyError('date')``，此时回退到 ``stock_zh_index_hist_csindex``
    （中证官网，对中证代码通用；实测 930955/000300/000016/000922/000905 均可用）。
    """
    try:
        import akshare as ak  # noqa: PLC0415

        df = ak.stock_zh_index_daily(symbol=_to_prefixed_symbol(index_code))
    except KeyError:
        # 中证代码（930xxx 等）交易所日线不收录 → akshare 内部 KeyError('date')，走回退源
        df = None
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"指数行情接口异常（{index_code}）：{e}") from e

    if df is None or df.empty or "date" not in df.columns or "close" not in df.columns:
        # 主源空或不收录 → 回退中证官网
        return _fetch_index_close_csindex(index_code, start, end)

    df = df[["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    bars: list[IndexBar] = []
    for _, row in df.iterrows():
        d = row["date"].date()
        if d < start or d > end:
            continue
        bars.append(
            IndexBar(
                index_code=index_code,
                trade_date=d,
                close=_to_dec(row["close"]),
                index_type="price",
                source="akshare_daily",
            )
        )
    # 主源区间内无数据（如 000922 中证红利交易所日线仅到 2019）→ 回退中证官网
    if not bars:
        return _fetch_index_close_csindex(index_code, start, end)
    return bars


def fetch_total_return_close(index_code: str, start: date, end: date) -> list[IndexBar]:
    """拉取 [start, end] 区间全收益指数收盘点位（``stock_zh_index_hist_csindex``，H 代码）。

    ⚠️ 必须显式传 start_date/end_date，否则该接口默认 end_date=20240604 会误判为数据过期。
    """
    try:
        import akshare as ak  # noqa: PLC0415

        df = ak.stock_zh_index_hist_csindex(
            symbol=index_code,
            start_date=start.strftime("%Y%m%d"),
            end_date=end.strftime("%Y%m%d"),
        )
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"全收益指数接口异常（{index_code}）：{e}") from e

    return _parse_csindex_df(df, index_code, start, end, "total_return", "akshare_csindex")
