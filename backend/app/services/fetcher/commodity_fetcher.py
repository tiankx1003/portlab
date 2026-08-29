"""大宗商品数据拉取（032）：期货主力连续 + BDI 运价指数。

不走 ``DataFetcher`` 抽象基类（与 signal_fetcher 一致——直接 ``import akshare``）。
异常统一抛 ``FetchError``（中文友好）。宽松 Decimal 转换复用 ``valuation_fetcher._to_dec``。

数据源（akshare 1.18.64 实测）：
- ``futures_zh_daily_sina``：新浪期货日线，``date``/``close`` 列，参数为主力连续代码（JM0 焦煤/CU0 沪铜/RB0 螺纹钢）。
- ``macro_china_freight_index``：波罗的海运价指数，``截止日期``/``波罗的海综合运价指数BDI`` 列，**降序**需翻转。
"""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pandas as pd

from .base import FetchError
from .valuation_fetcher import _to_dec

logger = logging.getLogger(__name__)

# 品种配置：(symbol, 中文名, 数据源类型)
# futures → futures_zh_daily_sina；bdi → macro_china_freight_index
_COMMODITY_SPECS: dict[str, tuple[str, str]] = {
    "JM0": ("焦煤主力", "futures"),
    "CU0": ("沪铜主力", "futures"),
    "RB0": ("螺纹钢主力", "futures"),
    "BDI": ("波罗的海运价指数", "bdi"),
}


@dataclass(frozen=True)
class CommodityBar:
    """大宗商品单日（字段对齐 ``raw_commodity_daily`` 表列）。"""

    symbol: str
    trade_date: date
    close: Decimal | None
    source: str


def _parse_date(v) -> date | None:
    """宽松日期解析：字符串/datetime/date → date。"""
    if isinstance(v, date):
        return v
    try:
        return pd.to_datetime(v).date()
    except Exception:  # noqa: BLE001
        return None


def fetch_commodity(symbol: str, start: date, end: date) -> list[CommodityBar]:
    """拉取 [start, end] 区间大宗商品收盘价。

    symbol ∈ {JM0, CU0, RB0, BDI}。futures 走新浪期货日线，BDI 走波罗的海运价指数。
    """
    spec = _COMMODITY_SPECS.get(symbol)
    if spec is None:
        raise FetchError(f"未知大宗商品代码：{symbol}")
    _, src_type = spec

    if src_type == "futures":
        return _fetch_futures(symbol, start, end)
    if src_type == "bdi":
        return _fetch_bdi(start, end)
    raise FetchError(f"未知数据源类型：{src_type}")


def _fetch_futures(symbol: str, start: date, end: date) -> list[CommodityBar]:
    """新浪期货日线（主力连续）。全量后按区间过滤。"""
    try:
        import akshare as ak  # noqa: PLC0415

        df = ak.futures_zh_daily_sina(symbol=symbol)
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"期货接口异常（{symbol}）：{e}") from e

    if df is None or df.empty or "date" not in df.columns or "close" not in df.columns:
        return []

    df = df[["date", "close"]].copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    bars: list[CommodityBar] = []
    for _, row in df.iterrows():
        d = row["date"].date()
        if d < start or d > end:
            continue
        bars.append(CommodityBar(symbol=symbol, trade_date=d, close=_to_dec(row["close"]), source="akshare_sina"))
    return bars


def _fetch_bdi(start: date, end: date) -> list[CommodityBar]:
    """波罗的海综合运价指数（BDI）。数据降序，需翻转；截止日期为字符串。"""
    try:
        import akshare as ak  # noqa: PLC0415

        df = ak.macro_china_freight_index()
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"BDI 接口异常：{e}") from e

    if df is None or df.empty or "截止日期" not in df.columns or "波罗的海综合运价指数BDI" not in df.columns:
        return []

    df = df[["截止日期", "波罗的海综合运价指数BDI"]].copy()
    df["截止日期"] = pd.to_datetime(df["截止日期"])
    df = df.sort_values("截止日期")
    bars: list[CommodityBar] = []
    for _, row in df.iterrows():
        d = row["截止日期"].date()
        if d < start or d > end:
            continue
        v = _to_dec(row["波罗的海综合运价指数BDI"])
        if v is None:
            continue
        bars.append(CommodityBar(symbol="BDI", trade_date=d, close=v, source="akshare_freight"))
    return bars


def list_commodity_symbols() -> list[dict]:
    """返回品种清单（供前端下拉/展示）。"""
    return [
        {"symbol": sym, "name_cn": name, "source": src}
        for sym, (name, src) in _COMMODITY_SPECS.items()
    ]
