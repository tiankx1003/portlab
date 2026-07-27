"""PE 估值通道 / 历史分位 / 多指数归一化（024 估值看板 v2）。

- ``percentile_rank``：从 016 ``valuation.py`` 内联逻辑迁出并标准化（去 NULL/NaN）。
- ``pe_channel``：用户明确指定的「min/median/max + 中点」5 线算法（非标准 25/50/75 分位）。
- ``channel_position``：当前 PE 落在 4 个带的文字判断（参考同花顺高估/低估）。
- ``normalize_to_base``：多指数叠加归一化（第 1 天 = base）。
"""

import statistics


def _clean(series: list[float | None]) -> list[float]:
    """去 NULL/NaN 并升序。"""
    return sorted(v for v in series if v is not None and v == v)  # v == v 排除 NaN


def percentile_rank(value: float, series: list[float]) -> float | None:
    """value 在 series 中的历史分位（0~100，越大越贵）。

    用「≤ value 的样本占比」定义，与 016 内联实现一致；空序列返回 None。
    """
    valid = _clean(series)
    if not valid:
        return None
    below = sum(1 for v in valid if v <= value)
    return round(below / len(valid) * 100, 2)


def pe_channel(pe_series: list[float | None]) -> dict:
    """5 条通道线（用户明确指定算法，非标准分位）：

    - L1 = 周期最小值
    - L3 = 中位数
    - L2 = (L1 + L3) / 2（最小值与中位数的平均值）
    - L4 = (L3 + L5) / 2（中位数与最大值的平均值）
    - L5 = 周期最大值
    """
    valid = _clean(pe_series)
    if not valid:
        return {}
    lo, hi, med = valid[0], valid[-1], statistics.median(valid)
    return {
        "l1_min": round(lo, 4),
        "l2_low": round((lo + med) / 2, 4),
        "l3_median": round(med, 4),
        "l4_high": round((med + hi) / 2, 4),
        "l5_max": round(hi, 4),
    }


def channel_position(current_pe: float | None, ch: dict) -> str:
    """当前 PE 落在 4 个带的哪一段（偏高估/中高/中低/偏低估）。"""
    if not ch or current_pe is None:
        return "—"
    if current_pe >= ch["l4_high"]:
        return "偏高估"
    if current_pe >= ch["l3_median"]:
        return "中高"
    if current_pe >= ch["l2_low"]:
        return "中低"
    return "偏低估"


def normalize_to_base(series: list[float | None], base: float = 1.0) -> list[float | None]:
    """多指数叠加归一化：第 1 个非空值 = base（1 或 1000），其余按比例。

    缺失值（None）保持 None。首个非空为 0 或全空时返回全 None。
    """
    out: list[float | None] = []
    first = next((v for v in series if v is not None), None)
    if first is None or first == 0:
        return [None] * len(series)
    for v in series:
        out.append(None if v is None else round(v / first * base, 4))
    return out
