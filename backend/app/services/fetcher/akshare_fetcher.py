"""AkShare 数据源实现。

数据通路策略：**东财优先、失败自动回退腾讯**。
- 东财 ``stock_zh_a_hist``：覆盖广、字段全，是多数环境下的主路径。
- 腾讯 ``stock_zh_a_hist_tx``：稳定性更好，且不受部分网络环境对东财接口的
  阻断/502 影响；当东财异常时自动降级到腾讯。

两者均取**前复权(qfq)**日线 OHLCV，便于后续回测还原真实收益。

symbol 约定：
- 东财接受裸 6 位代码（如 ``000001``）。
- 腾讯需要 ``sh``/``sz`` 前缀（如 ``sz000001``），本模块按代码首位自动判定。
"""

import os

os.environ.setdefault("TQDM_DISABLE", "1")  # 屏蔽腾讯接口内部的 tqdm 进度条

from datetime import date
from decimal import Decimal, InvalidOperation

import akshare as ak
import pandas as pd

from .base import DataFetcher, FetchError, PriceBar

# 东财中文表头 -> 内部字段
_EM_COL_MAP = {
    "日期": "trade_date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
}


class AkShareFetcher(DataFetcher):
    name = "akshare"

    def fetch_daily(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        errors: list[str] = []
        for impl in (_fetch_em, _fetch_tx):
            label = impl.__name__
            try:
                bars = impl(symbol, start_date, end_date)
            except FetchError as e:
                errors.append(f"{label}: {e}")
                continue
            except Exception as e:  # noqa: BLE001
                errors.append(f"{label}: {type(e).__name__}: {e}")
                continue
            if bars:
                return bars
            errors.append(f"{label}: 返回空")

        raise FetchError(f"所有数据源均失败 ({symbol}): " + " | ".join(errors))


def _fetch_em(symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
    try:
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"东财接口异常: {e}") from e

    if df is None or df.empty:
        return []
    df = df.rename(columns={k: v for k, v in _EM_COL_MAP.items() if k in df.columns})
    return _df_to_bars(df, symbol)


def _fetch_tx(symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
    try:
        df = ak.stock_zh_a_hist_tx(
            symbol=_to_tencent_symbol(symbol),
            start_date=start_date.strftime("%Y%m%d"),
            end_date=end_date.strftime("%Y%m%d"),
            adjust="qfq",
        )
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"腾讯接口异常: {e}") from e

    if df is None or df.empty:
        return []
    df = df.rename(columns={"date": "trade_date", "amount": "volume"})
    return _df_to_bars(df, symbol)


def _df_to_bars(df: pd.DataFrame, symbol: str) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for _, row in df.iterrows():
        bars.append(
            PriceBar(
                symbol=symbol,
                trade_date=pd.to_datetime(row["trade_date"]).date(),
                open=_to_decimal(row["open"]),
                close=_to_decimal(row["close"]),
                high=_to_decimal(row["high"]),
                low=_to_decimal(row["low"]),
                volume=_to_int(row.get("volume")),
            )
        )
    bars.sort(key=lambda b: b.trade_date)
    return bars


def _to_tencent_symbol(symbol: str) -> str:
    """裸代码 -> 腾讯代码（带交易所前缀）。"""
    s = symbol.strip().lower()
    if s.startswith(("sh", "sz", "bj")):
        return s
    if not s:
        raise FetchError("标的代码为空")
    head = s[0]
    if head in ("6", "5", "9"):  # 沪市主板 / 科创板 / ETF / B 股
        return "sh" + s
    if head in ("0", "3", "2"):  # 深市主板 / 创业板 / B 股
        return "sz" + s
    return "sz" + s  # 兜底按深市处理


def _to_decimal(v) -> Decimal:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        raise FetchError("价格为空，数据不完整")
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise FetchError(f"价格无法解析为数值: {v!r}") from e


def _to_int(v) -> int | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None
