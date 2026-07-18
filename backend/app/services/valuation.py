"""估值温度计 / 估值分位（016）：指数 PE 历史分位。

数据源 ``stock_index_pe_lg``（乐咕乐股）依赖 ``py_mini_racer`` 原生库；
当前容器环境该原生库缺失 → 接口优雅降级，返回 ``available=False`` 与修复方向，
待环境修复（装 py_mini_racer 原生库 / 换 PE 源）后自动恢复。
"""

import logging

logger = logging.getLogger(__name__)

# 代码 -> 指数名（stock_index_pe_lg 按中文名查询）
_INDEX_NAMES: dict[str, str] = {
    "000300": "沪深300",
    "000905": "中证500",
    "000852": "中证1000",
    "000016": "上证50",
    "399006": "创业板指",
}

_SUPPORTED = "、".join(f"{c}({n})" for c, n in _INDEX_NAMES.items())


def percentile(value: float, hist: list[float]) -> float | None:
    """value 在 hist 中的历史分位（0~100，越大越贵）。"""
    if not hist:
        return None
    below = sum(1 for v in hist if v <= value)
    return round(below / len(hist) * 100, 2)


def get_valuation(symbol: str) -> dict:
    name = _INDEX_NAMES.get(symbol)
    if not name:
        return {
            "available": False,
            "reason": f"暂未支持该代码的估值；支持：{_SUPPORTED}",
        }
    try:
        import akshare as ak  # noqa: PLC0415
    except Exception as e:  # noqa: BLE001
        return {"available": False, "reason": f"akshare 不可用：{e}"}

    try:
        df = ak.stock_index_pe_lg(symbol=name)
    except Exception as e:  # noqa: BLE001 - 数据源不可用：降级
        return {
            "available": False,
            "reason": (
                f"PE 数据源暂不可用（{type(e).__name__}: {str(e)[:90]}）。"
                "修复方向：容器内安装 py_mini_racer 原生库，或更换 PE 数据源。"
            ),
        }

    if df is None or len(df) == 0:
        return {"available": False, "reason": "PE 数据为空"}

    # 乐咕乐股列名：静态市盈率 / 滚动市盈率（优先静态）
    pe_col = next(
        (c for c in ("静态市盈率", "滚动市盈率", "市盈率") if c in df.columns), df.columns[-1]
    )
    date_col = "日期" if "日期" in df.columns else df.columns[0]
    # 按日期升序、丢 NaN；当前 PE = 最新一行，分位用全部历史
    df = df.sort_values(date_col).dropna(subset=[pe_col])
    dates = [str(x) for x in df[date_col].tolist()]
    pes = [float(v) for v in df[pe_col].tolist()]
    if not pes:
        return {"available": False, "reason": "PE 数据为空"}
    cur = pes[-1]
    hist = sorted(pes)
    series = list(zip(dates, pes, strict=False))
    return {
        "available": True,
        "symbol": symbol,
        "name": name,
        "current_pe": round(cur, 3),
        "percentile": percentile(cur, hist),
        "min": round(hist[0], 3),
        "max": round(hist[-1], 3),
        "as_of": str(df[date_col].iloc[-1]),
        "series": series[-300:],
    }
