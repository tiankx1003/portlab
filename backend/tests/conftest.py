"""pytest 共享夹具。

策略计算引擎（drawboard / grid / portfolio）的仿真核心都设计为纯函数：
输入行情序列，输出结果对象，不依赖 DB —— 便于单测、规避网络行情拉取。
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest


@pytest.fixture
def make_days():
    """工厂夹具：把价格序列转为 ``[(date, Decimal), ...]`` 行情，供纯函数引擎测试。

    日期从 ``start`` 起按日历日递增（与真实交易日序同构，足够驱动逐日遍历逻辑）。
    """

    def _make(prices: list[float], start: date = date(2024, 1, 1)) -> list[tuple[date, Decimal]]:
        return [(start + timedelta(days=i), Decimal(str(p))) for i, p in enumerate(prices)]

    return _make
