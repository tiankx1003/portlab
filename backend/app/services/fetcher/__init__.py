"""数据源工厂。根据 source 返回对应 Fetcher 实例（akshare / tushare）。"""

from .akshare_fetcher import AkShareFetcher
from .base import DataFetcher, FetchError, PriceBar
from .tushare_fetcher import TushareFetcher

__all__ = ["DataFetcher", "FetchError", "PriceBar", "get_fetcher"]

_FETCHERS: dict[str, type[DataFetcher]] = {
    "akshare": AkShareFetcher,
    "tushare": TushareFetcher,
}


def get_fetcher(source: str = "akshare") -> DataFetcher:
    key = (source or "akshare").strip().lower()
    cls = _FETCHERS.get(key)
    if cls is None:
        raise FetchError(f"不支持的数据源: {source!r}（当前支持: {', '.join(_FETCHERS)}）")
    return cls()
