"""网格交易（020）计算引擎单测 —— 纯函数 _simulate_grid / build_grid_levels。

仿真核心不依赖 DB；构造行情序列直接驱动双向触发逻辑。
"""

from decimal import Decimal

from app.services.compute.grid import _simulate_grid, build_grid_levels


def test_grid_levels_symmetric():
    """中枢 100、间距 3%、上下各 2 格 → [94, 97, 103, 106]，对称。"""
    levels = build_grid_levels(Decimal("100"), Decimal("3"), n_above=2, n_below=2)
    assert [float(x) for x in levels] == [94.0, 97.0, 103.0, 106.0]


def test_buy_on_dip_sell_on_rally(make_days):
    """跌穿下网格买入、涨破上网格卖出（FIFO），grid_profit = 卖出回款 − 买入成本。"""
    # 中枢 100：day1 穿 97 线买入；day2 穿 103 线卖出
    days = make_days([100, 96, 104])
    sim = _simulate_grid(days, Decimal("100"), Decimal("3"), Decimal("1000"), 2, 2, "hold")
    assert len(sim.buy_points) == 1
    assert len(sim.sell_points) == 1
    # 1000/96 份 × 104 − 1000 ≈ 83.33
    assert round(sim.grid_profit, 2) == 83.33
    assert sim.cycle_count == 1
    assert sim.rows[-1].holding == 0  # 配对卖出后清仓


def test_multi_level_cross_buys_multiple(make_days):
    """单日暴跌跨多格 → 跨过的每条线各买入一格。"""
    # 100 → 90 同时跌穿 97、94 两条线
    days = make_days([100, 90])
    sim = _simulate_grid(days, Decimal("100"), Decimal("3"), Decimal("1000"), 2, 2, "hold")
    assert len(sim.buy_points) == 2
    assert sim.total_invested == 2000


def test_bound_stop_liquidates_at_loss(make_days):
    """bound_mode=stop：跌破下沿止损清仓，认亏（grid_profit < 0）。"""
    # day1 穿 97 线买入；day2 穿 94 线买入且跌破下沿（94）→ 止损全清
    days = make_days([100, 96, 93])
    sim = _simulate_grid(days, Decimal("100"), Decimal("3"), Decimal("1000"), 2, 2, "stop")
    assert sim.rows[-1].holding == 0  # 清仓
    assert sim.grid_profit < 0  # 止损认亏
    assert sim.cycle_count >= 1


def test_bound_hold_keeps_position_beyond_grid(make_days):
    """bound_mode=hold：跌破下沿后不清仓，持仓等回归。"""
    days = make_days([100, 90])  # 穿 97、94 买入，跌破下沿 94
    sim = _simulate_grid(days, Decimal("100"), Decimal("3"), Decimal("1000"), 2, 2, "hold")
    assert sim.rows[-1].holding > 0  # 持仓保留
    assert len(sim.sell_points) == 0  # 不清仓
