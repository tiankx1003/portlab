"""组合回测（022）schema。

克隆 ma120/drawboard 四件套：Request / Created / ChartData / Summary。
ChartData 含 ``correlation_matrix``（相关性热力图）与 ``frontier``（有效前沿，frontier 模式）。
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from ..utils.symbol import strip_market_prefix


class FrontierPoint(BaseModel):
    weights: list[float]
    ret: float  # 年化收益 %（return 是 Python 关键字，用 ret）
    volatility: float  # 年化波动 %
    sharpe: float


class SingleAssetPoint(BaseModel):
    symbol: str
    name: str
    ret: float
    volatility: float
    sharpe: float


class FrontierData(BaseModel):
    volatilities: list[float]  # 前沿点波动率（连线用）
    returns: list[float]  # 前沿点收益
    sharpes: list[float]
    weights_matrix: list[list[float]]  # 每个前沿点的权重
    single_assets: list[SingleAssetPoint]  # 单标的 (波动,收益) 散点
    min_variance: FrontierPoint
    max_sharpe: FrontierPoint
    opt_weights: list[float]  # 最大夏普权重（前端饼图联动用）


class PortfolioChartData(BaseModel):
    dates: list[date]
    nav: list[float]  # 组合净值（起点=1）
    drawdown: list[float]
    benchmark_nav: list[float | None]  # 基准归一化净值（起点=1）
    benchmark_name: str
    correlation_symbols: list[str]
    correlation_matrix: list[list[float]]  # n×n 相关系数（-1~+1）
    mode: str
    symbols_name: list[str]
    frontier: FrontierData | None = None  # 仅 frontier 模式


class PortfolioSummaryData(BaseModel):
    symbols: list[str]
    mode: str
    weights: list[float]
    rebalance: str
    annual_return: float
    annual_volatility: float
    sharpe: float
    max_drawdown: float
    total_return: float
    rf: float
    allow_short: bool


class PortfolioRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=2, max_length=12)
    start_date: date
    end_date: date
    mode: Literal["fixed", "frontier"] = "fixed"
    weights: list[float] = Field(default_factory=list)  # fixed 模式必填
    rebalance: Literal["monthly", "quarterly", "none"] = "monthly"
    rf: float = Field(0.025, ge=0, le=0.2, description="无风险利率（小数，如 0.025）")
    allow_short: bool = False

    @field_validator("symbols")
    @classmethod
    def _normalize_symbols(cls, v: list[str]) -> list[str]:
        out: list[str] = []
        for s in v:
            code = strip_market_prefix(s)
            if not code:
                raise ValueError("标的代码不能为空")
            if code in out:
                raise ValueError(f"标的重复: {code}")
            out.append(code)
        if len(out) < 2:
            raise ValueError("组合回测需至少 2 个标的")
        return out

    @model_validator(mode="after")
    def _validate(self) -> "PortfolioRequest":
        if self.start_date >= self.end_date:
            raise ValueError("start_date 必须早于 end_date")
        if self.mode == "fixed" and len(self.weights) != len(self.symbols):
            raise ValueError("fixed 模式权重数需与标的数一致")
        return self


class PortfolioCreated(BaseModel):
    task_id: str
