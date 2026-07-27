"""估值看板 v2（024）纯函数单测 —— 分位 / PE 通道 / 通道位置 / 归一化。不依赖 DB。"""

from app.services.compute.valuation_metrics import (
    channel_position,
    normalize_to_base,
    pe_channel,
    percentile_rank,
)


def test_percentile_rank_basic_and_empty():
    assert percentile_rank(50, [10, 20, 30, 40, 50]) == 100.0  # 最大值 → 100%
    assert percentile_rank(5, [10, 20, 30]) == 0.0  # 低于全部 → 0%
    assert percentile_rank(30, [10, 20, 30, 40, 50]) == 60.0  # ≤30 的占 3/5
    assert percentile_rank(None, []) is None  # 空序列 → None
    assert percentile_rank(20, []) is None


def test_percentile_rank_ignores_none_and_nan():
    # None / NaN 被剔除，仅按有效值算分位
    assert percentile_rank(30, [10, None, 20, float("nan"), 30, 40, 50]) == 60.0


def test_pe_channel_user_algorithm():
    # min=10, max=50, median=20 → L2=(10+20)/2=15, L4=(20+50)/2=35
    ch = pe_channel([10, 12, 20, 30, 50])
    assert ch == {
        "l1_min": 10.0,
        "l2_low": 15.0,
        "l3_median": 20.0,
        "l4_high": 35.0,
        "l5_max": 50.0,
    }


def test_pe_channel_empty_and_none():
    assert pe_channel([]) == {}
    assert pe_channel([None, None]) == {}
    # 单点：min=max=median
    assert pe_channel([7.0]) == {
        "l1_min": 7.0,
        "l2_low": 7.0,
        "l3_median": 7.0,
        "l4_high": 7.0,
        "l5_max": 7.0,
    }


def test_channel_position_bands():
    ch = pe_channel([10, 20, 50])  # min10 med20 max50 → L2=15 L4=35
    assert channel_position(40, ch) == "偏高估"  # ≥ L4
    assert channel_position(25, ch) == "中高"  # L3..L4
    assert channel_position(16, ch) == "中低"  # L2..L3
    assert channel_position(11, ch) == "偏低估"  # < L2
    assert channel_position(None, ch) == "—"
    assert channel_position(40, {}) == "—"


def test_normalize_to_base():
    # 第 1 个非空 = base
    assert normalize_to_base([2, 4, None, 8], 1) == [1.0, 2.0, None, 4.0]
    assert normalize_to_base([2, 4, 8], 1000) == [1000.0, 2000.0, 4000.0]
    # 前导 None：首个非空为基准
    assert normalize_to_base([None, 5, 10], 1) == [None, 1.0, 2.0]
    # 全空 → 全 None
    assert normalize_to_base([None, None], 1) == [None, None]
    # 空 → 空
    assert normalize_to_base([], 1) == []
    # 基准为 0 → 全 None（避免除零）
    assert normalize_to_base([0, 1, 2], 1) == [None, None, None]
