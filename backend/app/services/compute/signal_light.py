"""信号灯阈值与三层共振判断（032）。

所有阈值忠实设计文档 ``docs/refer/估值与信号看板设计.md``。本期硬编码，「阈值可配」列开放问题。

信号语义：
- ``green``：便宜 / 底部特征 / 利好（对应设计文档 🟢）
- ``yellow``：中性 / 观察区（🟡）
- ``red``：昂贵 / 顶部特征 / 利空（🔴）
- ``grey``：数据缺失，不参与表决

三层共振：全绿=历史底部区域；全红=历史顶部；其余=不确定（95% 时间）。
"""

from typing import Literal

Light = Literal["green", "yellow", "red", "grey"]


def light_pe_percentile(pct: float | None) -> Light:
    """PE/PB 历史分位（0~100，越大越贵）。None → grey。

    <30% 🟢（便宜）/ 30-70% 🟡 / >70% 🔴（贵）。
    """
    if pct is None:
        return "grey"
    if pct < 30:
        return "green"
    if pct <= 70:
        return "yellow"
    return "red"


def light_equity_bond(ratio: float | None) -> Light:
    """股债比价（EP/国债，越高=股票越便宜）。None → grey。

    >2 🟢（股票极具吸引力）/ 1.5-2 🟡 / <1.5 🔴（股票偏贵）。
    """
    if ratio is None:
        return "grey"
    if ratio >= 2:
        return "green"
    if ratio >= 1.5:
        return "yellow"
    return "red"


def light_ma120_deviation(dev: float | None) -> Light:
    """MA120 偏离度（价格/MA120，>1=线上）。None → grey。

    <0.985 🟢（买入区）/ 0.985-1.05 🟡 / >1.05 🔴（高估区）。
    """
    if dev is None:
        return "grey"
    if dev < 0.985:
        return "green"
    if dev <= 1.05:
        return "yellow"
    return "red"


def light_drawdown(dd: float | None) -> Light:
    """当前回撤（%，>0）。None → grey。

    >15% 🟢（深跌机会）/ 5-15% 🟡 / <5% 🟡（无回撤，不便宜但也不贵）。
    """
    if dd is None:
        return "grey"
    if dd >= 15:
        return "green"
    return "yellow"


def light_mean_anchor(deviation: float | None) -> Light:
    """全收益 vs 5年均线 偏离度（%，>0=高于均线）。None → grey。

    <-10% 🟢（低估）/ -10%~+20% 🟡 / >+20% 🔴（过热）。
    """
    if deviation is None:
        return "grey"
    if deviation < -10:
        return "green"
    if deviation <= 20:
        return "yellow"
    return "red"


def light_fund_issue(scale_percentile: float | None) -> Light:
    """基金发行规模历史分位（0~100）。None → grey。

    <20% 🟢（冰点=底部信号）/ 20-80% 🟡 / >80% 🔴（过热=顶部信号）。
    """
    if scale_percentile is None:
        return "grey"
    if scale_percentile < 20:
        return "green"
    if scale_percentile <= 80:
        return "yellow"
    return "red"


def light_commodity(pct_change: float | None) -> Light:
    """大宗商品近期涨跌幅（%，>0=上行利好周期/红利成分股）。None → grey。

    >5% 🟢（上行，利好成分股利润）/ -5%~5% 🟡 / <-5% 🔴（下行，利润承压）。
    """
    if pct_change is None:
        return "grey"
    if pct_change >= 5:
        return "green"
    if pct_change <= -5:
        return "red"
    return "yellow"


def light_macro(indicator: str, value: float | None) -> Light:
    """宏观指标（各口径不同）。None → grey。

    - pmi: >50🟢（扩张）/ <50🔴（收缩）
    - m1m2_gap: 差值（m1_yoy - m2_yoy）收窄（>-2）🟢 / 扩大（<-2）🔴
    - sf_yoy: >0🟢（放量）/ <0🔴（收缩）
    - ppi_yoy: >0🟢（上行，利好周期/红利成分）/ <0🔴（下行）
    """
    if value is None:
        return "grey"
    if indicator == "pmi":
        return "green" if value >= 50 else "red"
    if indicator == "m1m2_gap":
        return "green" if value >= -2 else "red"
    if indicator in ("sf_yoy", "ppi_yoy"):
        return "green" if value >= 0 else "red"
    return "grey"


def light_margin_percentile(pct: float | None) -> Light:
    """融资余额历史分位（0~100，越高=杠杆越热）。None → grey。

    <20% 🟢（杠杆清洗充分=底部）/ >80% 🔴（散户加杠杆过热=顶部）。
    """
    if pct is None:
        return "grey"
    if pct < 20:
        return "green"
    if pct > 80:
        return "red"
    return "yellow"


def layer_summary(lights: list[Light]) -> Light:
    """单层汇总灯（多数表决）。grey 不参与表决。

    绿过半→green / 红过半→red / 否则→yellow。全部 grey 时返回 grey。
    """
    voting = [l for l in lights if l != "grey"]
    if not voting:
        return "grey"
    green = sum(1 for l in voting if l == "green")
    red = sum(1 for l in voting if l == "red")
    half = len(voting) / 2
    if green > half:
        return "green"
    if red > half:
        return "red"
    return "yellow"


def resonance(layer1: Light, layer2: Light, layer3: Light) -> tuple[str, str]:
    """三层共振判断 → (整体状态, 行动建议)。

    全绿→(🟢🟢🟢 历史底部区域, 重点关注，分批建仓区)
    全红→(🔴🔴🔴 历史顶部区域, 警惕，考虑减仓)
    其余→(🟡 不确定, 保持纪律，不做大动作)

    grey 视为非绿非红（不影响「全绿/全红」判定）。
    """
    layers = [layer1, layer2, layer3]
    real = [l for l in layers if l != "grey"]
    if real and all(l == "green" for l in real):
        return ("🟢🟢🟢 历史底部区域", "重点关注，分批建仓区")
    if real and all(l == "red" for l in real):
        return ("🔴🔴🔴 历史顶部区域", "警惕，考虑减仓")
    return ("🟡 不确定", "保持纪律，不做大动作")
