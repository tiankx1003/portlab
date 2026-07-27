"""chart 降采样与通用裁剪。

设计目标：把单次回测/看板曲线从 ~2500 点（日线 10 年）压到 ~80 点，
防止单次 tool 返回爆 LLM 上下文（~70K tokens），同时**不丢关键信息**：
  - 首尾点保留（趋势起止）；
  - 买卖信号日强制保留（buy_points / sell_points 命中的日期）；
  - 等间隔采样其余点；
  - 所有与 ``dates`` 等长的标量数组用**同一索引集**切片（曲线对齐）；
  - 嵌套小对象（correlation_matrix / frontier / channel / ranking）不降采样。

支持 backend 全部 chart 形状：
  - dca/ma120/grid/portfolio/drawboard chart：顶层 dates + 标量数组 + buy/sell_points。
  - drawboard series：dates 组 + benchmark_dates 组（各自降采样）。
  - valuation overlay：顶层 dates + series[].normalized（同步切片）。
  - arena compare：nav_series{task_id → {dates, nav}}（按各自 dates 降采样）。
  - event impact：window_returns{symbol → {dates, returns}} + benchmark_series
    （按各自 dates 降采样）。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

# 这些键是「对象数组 / 小矩阵 / 元数据」，不参与 dates 索引切片。
_PRESERVE_KEYS = frozenset(
    {
        "buy_points",
        "sell_points",
        "grid_levels",  # grid 网格线（markLine，少量）
        "correlation_matrix",  # n×n 矩阵
        "frontier",  # 有效前沿（嵌套对象）
        "channel",  # PE 通道（5 个标量，非时间序列）
        "series",  # overlay 子项数组（单独处理）
        "nav_series",  # arena dict（单独处理）
        "window_returns",  # event dict（单独处理）
        "benchmark_series",  # event 单对象（单独处理）
        "ranking",  # event 涨跌排行（少量对象）
        "symbols_info",
        "chain_groups",
        "single_assets",
        "items",
        "_meta",
    }
)

# signals 是 list[str]，长度 == dates，需要随主曲线切片；从 _PRESERVE 排除。
_SLICE_STRING_LISTS = frozenset({"signals"})


def _is_scalar_list(v: Any) -> bool:
    """list 且元素是标量（str/int/float/bool/None），非嵌套 list/dict。"""
    if not isinstance(v, list) or not v:
        return False
    return not isinstance(v[0], (list, dict))


def _index_set(dates: list, target: int, signal_dates: Iterable = ()) -> list[int] | None:
    """为长度 n 的 dates 生成降采样索引集；n <= target 时返回 None（无需采样）。

    总点数控制在 ~target：先为 signal_dates（买卖信号日）预留名额，
    剩余名额做均匀 linspace（含首尾），再并入信号日。
    这样信号日全部保留，且总点数 ≈ target
    （信号数 ≥ target 时退化为「信号日 + 20 个底点」）。
    """
    n = len(dates)
    if n <= target:
        return None
    date_to_i: dict[str, int] = {}
    for i, d in enumerate(dates):
        key = d.isoformat() if hasattr(d, "isoformat") else str(d)
        date_to_i.setdefault(key, i)
    sig_idx: set[int] = set()
    for d in signal_dates:
        key = d.isoformat() if hasattr(d, "isoformat") else str(d)
        if key in date_to_i:
            sig_idx.add(date_to_i[key])

    base = max(20, target - len(sig_idx))  # 给信号日留出名额后的均匀采样点数
    span = max(1, base - 1)
    idx = {int(round(i * (n - 1) / span)) for i in range(base)}
    idx.add(0)
    idx.add(n - 1)
    idx |= sig_idx
    return sorted(idx)


def _collect_signal_dates(obj: dict) -> list:
    """从 buy_points / sell_points 提取 date 值（保留信号日）。"""
    out: list = []
    for key in ("buy_points", "sell_points"):
        for pt in obj.get(key, []) or []:
            if isinstance(pt, dict) and pt.get("date") is not None:
                out.append(pt["date"])
    return out


def _slice_scalar_lists(obj: dict, idx: list[int], n: int) -> dict:
    """对 obj 中所有与 dates 等长（==n）的标量数组按 idx 切片；保留对象/小数组。"""
    out = dict(obj)
    for k, v in obj.items():
        if k in _PRESERVE_KEYS:
            continue
        if k == "dates":
            out[k] = [v[i] for i in idx]
        elif k in _SLICE_STRING_LISTS and isinstance(v, list) and len(v) == n:
            out[k] = [v[i] for i in idx]
        elif _is_scalar_list(v) and len(v) == n:
            out[k] = [v[i] for i in idx]
    return out


def downsample_chart(data: Any, target_points: int = 80) -> Any:
    """主入口：按策略裁剪 chart 数据。非 dict 原样返回。"""
    if not isinstance(data, dict):
        return data
    out: dict[str, Any] = dict(data)

    dates = data.get("dates")
    if isinstance(dates, list) and dates:
        n = len(dates)
        idx = _index_set(dates, target_points, _collect_signal_dates(data))
        if idx is not None:
            out = _slice_scalar_lists(out, idx, n)
            out["_meta"] = {"original_len": n, "sampled_len": len(idx), "sampled": True}

        # overlay：series[].normalized 与顶层 dates 等长 → 同步切片
        if isinstance(data.get("series"), list):
            out["series"] = [_slice_overlay_item(it, idx, n) for it in data["series"]]

    # arena / event：dict[*, {dates, ...}] → 各自按自身 dates 降采样
    for dict_key in ("nav_series", "window_returns"):
        val = data.get(dict_key)
        if isinstance(val, dict):
            out[dict_key] = {
                k: (downsample_chart(v, target_points) if isinstance(v, dict) else v)
                for k, v in val.items()
            }

    # event benchmark_series：单个 {dates, returns}
    bs = data.get("benchmark_series")
    if isinstance(bs, dict):
        out["benchmark_series"] = downsample_chart(bs, target_points)

    # drawboard series：benchmark_dates 组（可能与 dates 不同长）→ 按自身索引切片
    bdates = data.get("benchmark_dates")
    if isinstance(bdates, list) and bdates:
        bidx = _index_set(bdates, target_points)
        if bidx is not None:
            nb = len(bdates)
            out["benchmark_dates"] = [bdates[i] for i in bidx]
            for k, v in data.items():
                if (
                    k.startswith("benchmark_")
                    and k != "benchmark_dates"
                    and _is_scalar_list(v)
                    and len(v) == nb
                ):
                    out[k] = [v[i] for i in bidx]

    return out


def _slice_overlay_item(item: Any, idx: list[int] | None, n: int) -> Any:
    """overlay 单个 series 项：把与 dates 等长的标量数组（normalized 等）同步切片。"""
    if not isinstance(item, dict) or idx is None:
        return item
    out = dict(item)
    for k, v in item.items():
        if _is_scalar_list(v) and len(v) == n:
            out[k] = [v[i] for i in idx]
    return out


def apply_sample(data: Any, sample: str, target_points: int = 80) -> Any:
    """按 registry 的 sample 策略分发。

    - ``none``：原样返回。
    - ``chart80`` / ``event_impact``：走 downsample_chart（event_impact 的 window_returns
      / benchmark_series 由 downsample_chart 内部递归处理，逻辑一致）。
    """
    if data is None:
        return None
    if sample in ("chart80", "event_impact"):
        return downsample_chart(data, target_points)
    return data
