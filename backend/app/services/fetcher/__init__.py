"""数据源工厂。根据配置（DATA_SOURCE）返回对应 Fetcher 实例。"""

from .akshare_fetcher import AkShareFetcher
from .base import DataFetcher, FetchError, PriceBar

__all__ = ["DataFetcher", "FetchError", "PriceBar", "get_fetcher"]

_FETCHERS: dict[str, type[DataFetcher]] = {
    "akshare": AkShareFetcher,
}


def get_fetcher(source: str = "akshare") -> DataFetcher:
    key = (source or "akshare").strip().lower()
    cls = _FETCHERS.get(key)
    if cls is None:
        raise FetchError(f"不支持的数据源: {source!r}（当前支持: {', '.join(_FETCHERS)}）")
    return cls()
