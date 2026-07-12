"""数据拉取抽象基类与公共数据结构。后续可扩展更多数据源（Tushare/聚宽等）。"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


class FetchError(Exception):
    """数据拉取过程中的业务异常，消息会原样返回给调用方。"""


@dataclass(frozen=True)
class PriceBar:
    symbol: str
    trade_date: date
    open: Decimal
    close: Decimal
    high: Decimal
    low: Decimal
    volume: int | None


class DataFetcher(ABC):
    """数据拉取器接口。"""

    name: str = "base"

    @abstractmethod
    def fetch_daily(
        self, symbol: str, start_date: date, end_date: date
    ) -> list[PriceBar]:
        """按标的代码 + 日期范围拉取日线 OHLCV 行情。"""
        raise NotImplementedError
