"""股债比价滚动通道计算（032，吸收 027）。

- ``rolling_channel``：逐日计算过去 N 年窗口内的均值 + ±1/±2/±3 标准差。
  与 024 的 ``pe_channel``（全周期 min/median/max 静态 5 线）不同，这里每个交易日
  输出一组随时间漂移的通道线，还原「均值 + 标准差带」的经典 FED 模型视图。
- ``channel_position``：当前比价相对均值的偏离档位（便宜/中性/昂贵）。
- 窗口按**日期差**截取子序列（而非固定交易日数），更贴近「过去 5 年」的直觉。
"""

import statistics
from datetime import date, timedelta


def rolling_channel(
    series: list[float | None],
    dates: list[date],
    window_years: int = 5,
) -> dict[str, list[float | None]]:
    """滚动均值 + ±1/±2/±3σ 通道。

    对每个非空 ``i``，取 ``dates[i]`` 往前 ``window_years`` 年内的非空样本，
    计算均值 ``mean`` 与标准差 ``std``，输出 7 条与 ``series`` 等长的序列：
    ``mean`` / ``p1,p2,p3``（均值+Nσ）/ ``n1,n2,n3``（均值-Nσ）。

    前段（窗口内样本不足 2 个，无法算 std）对应位置为 ``None``。
    None 输入位置在所有输出序列中保持 ``None``。
    """
    n = len(series)
    mean: list[float | None] = [None] * n
    p1 = [None] * n
    p2 = [None] * n
    p3 = [None] * n
    n1 = [None] * n
    n2 = [None] * n
    n3 = [None] * n
    cutoff_delta = timedelta(days=int(window_years * 365.25))

    # 非空样本的原序列索引列表（升序），便于向前扫描定位窗口左端
    valid_idx = [i for i, v in enumerate(series) if v is not None]

    for pos, i in enumerate(valid_idx):
        d = dates[i]
        cutoff = d - cutoff_delta
        # 从 pos 向前取，直到日期 < cutoff
        window: list[float] = []
        for k in range(pos, -1, -1):
            j = valid_idx[k]
            if dates[j] < cutoff:
                break
            window.append(series[j])  # type: ignore[arg-type]  # valid_idx 保证非 None
        if not window:
            continue
        m = statistics.fmean(window)
        mean[i] = round(m, 4)
        if len(window) < 2:
            continue  # 单点有均值但无标准差
        s = statistics.pstdev(window)  # 总体标准差，与「通道带」直觉一致
        p1[i] = round(m + s, 4)
        p2[i] = round(m + 2 * s, 4)
        p3[i] = round(m + 3 * s, 4)
        n1[i] = round(m - s, 4)
        n2[i] = round(m - 2 * s, 4)
        n3[i] = round(m - 3 * s, 4)

    return {"mean": mean, "p1": p1, "p2": p2, "p3": p3, "n1": n1, "n2": n2, "n3": n3}


def channel_position(
    current_ratio: float | None,
    current_mean: float | None,
    current_p1: float | None,
    current_p2: float | None,
    current_n1: float | None,
    current_n2: float | None,
) -> str:
    """当前比价落在通道的哪一档（比价越高=股票越便宜）。

    档位（从贵到便宜）：
    - ``极度昂贵``：< -2σ　``昂贵``：[-2σ, -1σ)　``偏贵``：[-1σ, 均值)
    - ``中性``：[均值, +1σ)　``偏便宜``：[+1σ, +2σ)　``便宜``：≥ +2σ
    """
    if current_ratio is None or current_mean is None:
        return "—"
    if current_n2 is not None and current_ratio < current_n2:
        return "极度昂贵"
    if current_n1 is not None and current_ratio < current_n1:
        return "昂贵"
    if current_ratio < current_mean:
        return "偏贵"
    if current_p1 is not None and current_ratio < current_p1:
        return "中性"
    if current_p2 is not None and current_ratio < current_p2:
        return "偏便宜"
    return "便宜"
