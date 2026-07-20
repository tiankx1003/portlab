"""组合回测（022）计算引擎单测 —— 纯函数（协方差/有效前沿/净值/回撤）。

不依赖 DB；构造两条随机收盘序列驱动 numpy/scipy 逻辑。
"""

import datetime

import numpy as np

from app.services.compute.portfolio import (
    annualized_moments,
    backtest_nav_series,
    correlation_matrix,
    drawdown_series,
    efficient_frontier,
    max_sharpe_weights,
    min_variance_weights,
    portfolio_stats,
)


def _make_closes():
    rng = np.random.default_rng(42)
    s1 = 100 * np.cumprod(1 + rng.normal(0.0005, 0.01, 300))
    s2 = 100 * np.cumprod(1 + rng.normal(0.0003, 0.015, 300))
    return {"A": s1, "B": s2}, ["A", "B"]


def _dates(n):
    return [datetime.date(2020, 1, 1) + datetime.timedelta(days=i) for i in range(n)]


def test_correlation_symmetric_diag_one():
    closes, syms = _make_closes()
    corr = correlation_matrix(closes, syms)
    assert corr.shape == (2, 2)
    assert abs(corr[0, 0] - 1) < 1e-9
    assert abs(corr[1, 1] - 1) < 1e-9
    assert abs(corr[0, 1] - corr[1, 0]) < 1e-9


def test_portfolio_stats_positive_drift():
    closes, syms = _make_closes()
    mean, cov = annualized_moments(closes, syms)
    s = portfolio_stats([0.5, 0.5], mean, cov, 0.025)
    assert s["volatility"] > 0
    assert -1 < s["sharpe"] < 5  # 合理区间


def test_efficient_frontier_nonempty():
    closes, syms = _make_closes()
    mean, cov = annualized_moments(closes, syms)
    fr = efficient_frontier(mean, cov, 0.025, n_points=20)
    assert len(fr) >= 10  # 大部分 SLSQP 应收敛
    assert all(p["volatility"] > 0 for p in fr)
    # 收益升序排列
    rets = [p["return"] for p in fr]
    assert rets == sorted(rets)


def test_min_variance_not_worse_than_singles():
    """最小方差组合波动 ≤ 任意单标的波动。"""
    closes, syms = _make_closes()
    mean, cov = annualized_moments(closes, syms)
    mv = min_variance_weights(mean, cov, allow_short=False)
    mv_vol = portfolio_stats(mv, mean, cov)["volatility"]
    vol_a = portfolio_stats([1.0, 0.0], mean, cov)["volatility"]
    vol_b = portfolio_stats([0.0, 1.0], mean, cov)["volatility"]
    assert mv_vol <= max(vol_a, vol_b) + 1e-6


def test_max_sharpe_weights_sum_to_one():
    closes, syms = _make_closes()
    mean, cov = annualized_moments(closes, syms)
    ms = max_sharpe_weights(mean, cov, 0.025, allow_short=False)
    assert abs(sum(ms) - 1.0) < 1e-3
    assert all(w >= -1e-6 for w in ms)  # 不允许做空时非负


def test_nav_series_starts_at_one():
    closes, syms = _make_closes()
    navs = backtest_nav_series(closes, syms, [0.5, 0.5], _dates(len(closes["A"])), "monthly")
    assert abs(navs[0] - 1.0) < 1e-9
    assert len(navs) == len(closes["A"])


def test_drawdown_nonpositive():
    dd = drawdown_series([1.0, 1.2, 0.9, 1.1])
    assert all(x <= 1e-9 for x in dd)
    # 0.9 相对峰值 1.2 → -25%
    assert abs(dd[2] - (-25.0)) < 1e-6
