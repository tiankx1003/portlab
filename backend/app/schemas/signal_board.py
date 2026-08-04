"""估值与信号看板 Schema（032）。"""

from datetime import date
from typing import Literal

from pydantic import BaseModel

Light = Literal["green", "yellow", "red", "grey"]


class SignalItem(BaseModel):
    """单个指标信号。"""

    key: str
    label: str
    value: float | None = None
    display: str = "—"
    light: Light = "grey"
    hint: str | None = None


class ChartSeries(BaseModel):
    """图表数据（PE通道/股债比价/均值之锚通用）。"""

    dates: list[str] = []
    series: dict[str, list[float | None]] = {}


class TargetSignalsData(BaseModel):
    """第一层：单标的多维信号。"""

    symbol: str
    name_cn: str
    resolved_index: str | None = None
    as_of: str | None = None
    metrics: list[SignalItem] = []
    layer_light: Light = "grey"
    pe_channel_chart: ChartSeries | None = None
    equity_bond_chart: ChartSeries | None = None
    warning: str | None = None


class MarketSignalsData(BaseModel):
    """第二层：大类资产估值。"""

    as_of: str | None = None
    metrics: list[SignalItem] = []
    layer_light: Light = "grey"
    mean_anchor_chart: ChartSeries | None = None
    equity_bond_chart: ChartSeries | None = None
    ratio_chart: ChartSeries | None = None
    warning: str | None = None


class CapitalMacroSignalsData(BaseModel):
    """第三层：资金 + 宏观。"""

    as_of: str | None = None
    metrics: list[SignalItem] = []
    layer_light: Light = "grey"
    warning: str | None = None


class ResonanceData(BaseModel):
    """三层共振汇总。"""

    layer1: Light = "grey"
    layer2: Light = "grey"
    layer3: Light = "grey"
    overall_status: str = "—"
    action_advice: str = "—"
    as_of: str | None = None
