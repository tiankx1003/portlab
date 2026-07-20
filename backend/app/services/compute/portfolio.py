"""组合回测计算引擎（022）—— 从单标的到多标的组合。

两种模式：
- ``fixed``：用户指定权重，算组合净值时序（定期再平衡）+ 年化收益/波动/夏普 + 相关性矩阵。
- ``frontier``：马科维茨 MPT，用 scipy SLSQP 求有效前沿 + 最小方差/最大夏普组合。

数学依赖：numpy（协方差/矩阵）、scipy.optimize.minimize（有效前沿二次规划）。
数据层走 ``compute.common.load_prices``；均值/协方差/前沿/净值时序均为纯函数，便于单测。
金额用 float（numpy 友好）；落库时 nav/drawdown 量化。task_id 全参数确定性，幂等（先删后写）。
"""

import hashlib
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np
from scipy.optimize import minimize
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...models.portfolio import CalcPortfolioNav, ResultPortfolioSummary
from .common import load_prices, max_drawdown

TRADING_DAYS = 252
_Q4 = Decimal("0.0001")
_Q6 = Decimal("0.000001")

MODES = ("fixed", "frontier")
REBALANCES = ("monthly", "quarterly", "none")


class ComputeError(Exception):
    """回测计算业务异常。"""


# --------------------------- 数据加载与对齐（纯函数，db 仅读行情）---------------------------


def load_aligned_closes(
    db: Session, symbols: list[str], start: date, end: date, source: str
) -> tuple[list[date], dict[str, np.ndarray]]:
    """多标的收盘价，按日期取交集对齐，返回 (公共交易日, {symbol: 价格数组})。"""
    per_sym: dict[str, dict[date, float]] = {}
    for s in symbols:
        days = load_prices(db, s, start, end, source)
        per_sym[s] = {d: float(c) for d, c in days}
    common = sorted(set.intersection(*[set(per_sym[s]) for s in symbols])) if symbols else []
    closes = {s: np.array([per_sym[s][d] for d in common], dtype=float) for s in symbols}
    return common, closes


def _returns_matrix(closes: dict[str, np.ndarray], symbols: list[str]) -> np.ndarray:
    """日收益率矩阵 (n_symbols × (n_days-1))。"""
    return np.vstack([np.diff(closes[s]) / closes[s][:-1] for s in symbols])


def annualized_moments(
    closes: dict[str, np.ndarray], symbols: list[str]
) -> tuple[np.ndarray, np.ndarray]:
    """年化均值收益向量 + 年化协方差矩阵。"""
    r = _returns_matrix(closes, symbols)
    return r.mean(axis=1) * TRADING_DAYS, np.cov(r) * TRADING_DAYS


def correlation_matrix(closes: dict[str, np.ndarray], symbols: list[str]) -> np.ndarray:
    """标的间相关系数矩阵 (n×n)。"""
    return np.corrcoef(_returns_matrix(closes, symbols))


# --------------------------- 组合统计（纯函数）---------------------------


def portfolio_stats(
    weights, mean_returns: np.ndarray, cov_matrix: np.ndarray, rf: float = 0.025
) -> dict:
    """给定权重，算组合年化收益 / 年化波动 / 夏普。"""
    w = np.asarray(weights, dtype=float)
    ret = float(np.dot(w, mean_returns))
    var = float(np.dot(w, np.dot(cov_matrix, w)))
    vol = float(np.sqrt(max(var, 0.0)))
    sharpe = (ret - rf) / vol if vol > 0 else 0.0
    return {"return": ret, "volatility": vol, "sharpe": float(sharpe)}


def drawdown_series(navs: list[float]) -> list[float]:
    """净值序列的逐日回撤 %（≤0，0=新高）。"""
    peak = navs[0] if navs else 0.0
    out: list[float] = []
    for v in navs:
        if v > peak:
            peak = v
        out.append((v / peak - 1) * 100 if peak > 0 else 0.0)
    return out


# --------------------------- 有效前沿（scipy SLSQP）---------------------------


def _bounds(n: int, allow_short: bool) -> list[tuple]:
    return [(None, None)] * n if allow_short else [(0.0, 1.0)] * n


def _solve(obj, n: int, allow_short: bool, cons, x0=None) -> np.ndarray:
    res = minimize(
        obj, np.full(n, 1.0 / n) if x0 is None else x0,
        method="SLSQP", bounds=_bounds(n, allow_short), constraints=cons,
        options={"maxiter": 500, "ftol": 1e-9},
    )
    return res.x if res.success else np.full(n, 1.0 / n)


def min_variance_weights(
    mean_returns: np.ndarray, cov_matrix: np.ndarray, allow_short: bool
) -> np.ndarray:
    n = len(mean_returns)
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    return _solve(
        lambda w: float(np.dot(w, np.dot(cov_matrix, w))), n, allow_short, cons
    )


def max_sharpe_weights(
    mean_returns: np.ndarray, cov_matrix: np.ndarray, rf: float, allow_short: bool
) -> np.ndarray:
    n = len(mean_returns)

    def neg_sharpe(w):
        return -portfolio_stats(w, mean_returns, cov_matrix, rf)["sharpe"]

    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    return _solve(neg_sharpe, n, allow_short, cons)


def efficient_frontier(
    mean_returns: np.ndarray, cov_matrix: np.ndarray, rf: float = 0.025,
    n_points: int = 20, allow_short: bool = False,
) -> list[dict]:
    """求有效前沿 n_points 个最优组合（每个目标收益水平最小化方差）。

    返回 [{weights, return, volatility, sharpe}]，按收益升序。
    """
    n = len(mean_returns)
    if n == 0:
        return []
    lo = float(mean_returns.min())
    hi = float(mean_returns.max())
    if hi <= lo:
        hi = lo + 1e-6
    cons_base = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    points: list[dict] = []
    for tr in np.linspace(lo, hi, n_points):
        cons = cons_base + [
            {"type": "eq", "fun": lambda w, tr=tr: float(np.dot(w, mean_returns) - tr)}
        ]
        w = _solve(
            lambda w: float(np.dot(w, np.dot(cov_matrix, w))), n, allow_short, cons
        )
        s = portfolio_stats(w, mean_returns, cov_matrix, rf)
        points.append({"weights": w.tolist(), **s})
    points.sort(key=lambda p: p["return"])
    return points


# --------------------------- 指定权重净值时序（定期再平衡）---------------------------


def backtest_nav_series(
    closes: dict[str, np.ndarray], symbols: list[str], weights, dates: list[date],
    rebalance: str = "monthly",
) -> list[float]:
    """组合净值时序（起点=1）。再平衡 monthly/quarterly/none（none=买入持有，让权重漂移）。"""
    w = np.asarray(weights, dtype=float)
    if len(dates) < 2:
        return [1.0]
    nav = 1.0
    cur_w = w.copy()
    navs = [1.0]
    prev = (dates[0].year, dates[0].month)
    for i in range(1, len(dates)):
        rets = np.array([closes[s][i] / closes[s][i - 1] - 1 for s in symbols])
        nav *= 1 + float(np.dot(cur_w, rets))
        # 权重随各标的收益漂移
        grown = cur_w * (1 + rets)
        total = grown.sum()
        cur_w = grown / total if total != 0 else cur_w
        # 再平衡：到新月/新季首个交易日，调回目标权重
        ym = (dates[i].year, dates[i].month)
        need = False
        if rebalance == "monthly" and ym != prev:
            need = True
        elif rebalance == "quarterly" and (
            ym[0] != prev[0] or (ym[1] - 1) // 3 != (prev[1] - 1) // 3
        ):
            need = True
        if need:
            cur_w = w.copy()
        prev = ym
        navs.append(nav)
    return navs


# --------------------------- 落库回测（POST，task_id 幂等）---------------------------


@dataclass(frozen=True)
class PortfolioParams:
    symbols: tuple[str, ...]
    start_date: date
    end_date: date
    mode: str  # fixed/frontier
    weights: tuple[float, ...]  # fixed 模式用；frontier 存最大夏普权重
    rebalance: str  # monthly/quarterly/none
    rf: float
    allow_short: bool
    source: str = "akshare"


def make_task_id(p: PortfolioParams) -> str:
    sym_hash = hashlib.md5(",".join(sorted(p.symbols)).encode()).hexdigest()[:8]
    w_str = ",".join(f"{w:.4f}" for w in p.weights)
    w_hash = hashlib.md5(w_str.encode()).hexdigest()[:8] if p.weights else "equal"
    base = (
        f"port_{sym_hash}_{p.start_date:%Y%m%d}_{p.end_date:%Y%m%d}"
        f"_{p.mode}_{w_hash}_{p.rebalance}_{p.rf}_{int(p.allow_short)}"
    )
    return f"{base}_{p.source}" if p.source != "akshare" else base


def _resolve_weights(p: PortfolioParams, mean: np.ndarray, cov: np.ndarray) -> list[float]:
    """fixed 用用户权重；frontier 用最大夏普权重。"""
    if p.mode == "fixed":
        if len(p.weights) != len(p.symbols):
            raise ComputeError("权重数与标的数不符")
        if abs(sum(p.weights) - 1.0) > 0.01:
            raise ComputeError("权重之和需 ≈ 1（±0.01 容差）")
        return list(p.weights)
    return max_sharpe_weights(mean, cov, p.rf, p.allow_short).tolist()


def run_backtest(db: Session, p: PortfolioParams) -> str:
    """执行组合回测，逐日净值写入 calc_portfolio_nav，汇总写入 result_portfolio_summary。"""
    if p.mode not in MODES:
        raise ComputeError(f"不支持的模式: {p.mode}（可选 fixed/frontier）")
    if p.rebalance not in REBALANCES:
        raise ComputeError(f"不支持的再平衡: {p.rebalance}")
    if len(p.symbols) < 2:
        raise ComputeError("组合回测需至少 2 个标的")

    dates, closes = load_aligned_closes(db, list(p.symbols), p.start_date, p.end_date, p.source)
    if len(dates) < 2:
        raise ComputeError("标的交集行情不足 2 个交易日，请先拉取数据或扩大区间")

    mean, cov = annualized_moments(closes, list(p.symbols))
    weights = _resolve_weights(p, mean, cov)
    navs = backtest_nav_series(closes, list(p.symbols), weights, dates, p.rebalance)
    dds = drawdown_series(navs)
    stats = portfolio_stats(weights, mean, cov, p.rf)
    total_return = (navs[-1] - 1) * 100
    mdd = max_drawdown(navs)

    task_id = make_task_id(p)
    calc_rows = [
        CalcPortfolioNav(
            task_id=task_id,
            trade_date=dates[i],
            nav=Decimal(str(round(navs[i], 6))).quantize(_Q6),
            drawdown=Decimal(str(round(dds[i], 4))).quantize(_Q4),
        )
        for i in range(len(dates))
    ]
    summary = ResultPortfolioSummary(
        task_id=task_id,
        symbols=",".join(p.symbols),
        mode=p.mode,
        weights=_weights_to_str(weights),
        rebalance=p.rebalance,
        start_date=p.start_date,
        end_date=p.end_date,
        annual_return=Decimal(str(round(stats["return"] * 100, 4))).quantize(_Q4),
        annual_volatility=Decimal(str(round(stats["volatility"] * 100, 4))).quantize(_Q4),
        sharpe=Decimal(str(round(stats["sharpe"], 4))).quantize(_Q4),
        max_drawdown=Decimal(str(round(mdd, 4))).quantize(_Q4),
        total_return=Decimal(str(round(total_return, 4))).quantize(_Q4),
        rf=Decimal(str(round(p.rf, 4))).quantize(_Q4),
        allow_short=int(p.allow_short),
    )
    _write_results(db, task_id, calc_rows, summary)
    return task_id


def _weights_to_str(weights: list[float]) -> str:
    """权重序列存为逗号分隔字符串（前端解析为饼图/列表）。"""
    return ",".join(f"{w:.4f}" for w in weights)


def _write_results(db, task_id, calc_rows, summary) -> None:
    db.execute(delete(CalcPortfolioNav).where(CalcPortfolioNav.task_id == task_id))
    db.execute(delete(ResultPortfolioSummary).where(ResultPortfolioSummary.task_id == task_id))
    db.add_all(calc_rows)
    db.add(summary)
    db.commit()


# --------------------------- DB 读取（GET chart/summary）---------------------------


def load_nav_rows(db: Session, task_id: str) -> list[CalcPortfolioNav]:
    return (
        db.execute(
            select(CalcPortfolioNav)
            .where(CalcPortfolioNav.task_id == task_id)
            .order_by(CalcPortfolioNav.trade_date)
        )
        .scalars()
        .all()
    )
