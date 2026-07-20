"""drawboard（019）仿真核心单测 —— 验证买入阶梯锚点修复与 sell_mode 三模式。

``_simulate`` 是纯函数（输入行情序列，输出 ``_SimResult``），不依赖 DB。
"""

from app.services.drawboard import _simulate


def test_ladder_resumes_after_gap(make_days):
    """019 修复：单日缺口不把买入锚点拉深，后续理想档位仍能触发加仓。

    threshold=10、step=5 → 理想买入档位 -10% / -15% / -20% / ...
    旧逻辑锚定「实际买入回撤」：在 -17% 买入后锚点拉到 -17%，下一档门槛 -22%，
    -20% 档再也不触发（丢失补仓）。新逻辑锚定「理想档位」，-20% 档正常触发。
    """
    days = make_days([100, 89, 83, 84, 80])  # dd: 0, -11%, -17%, -16%, -20%
    sim = _simulate(
        days, threshold_pct=10, step_pct=5, buy_amount=10000, add_amount=5000, sell_mode="none"
    )
    # 3 笔买入：day1 首笔(10000) → day2 加仓(5000) → day4 加仓(5000，-20% 档)
    assert len(sim.buy_points) == 3
    assert sim.buy_points[0]["amount"] == 10000
    assert sim.buy_points[1]["amount"] == 5000
    assert sim.buy_points[2]["amount"] == 5000
    assert sim.buy_points[2]["price"] == 80  # -20% 档被触发（旧 bug 会丢这一笔）


def test_sell_modes(make_days):
    """sell_mode 三模式：none 只买不卖 / new_high 新高全清 / partial 卖一半留底仓。"""
    days = make_days([100, 85, 100])  # V 型：day1 -15%，day2 回到高点（dd=0 新高）

    s_none = _simulate(days, 10, 5, 10000, 5000, "none")
    assert len(s_none.sell_points) == 0
    assert len(s_none.buy_points) == 1

    s_new_high = _simulate(days, 10, 5, 10000, 5000, "new_high")
    assert len(s_new_high.sell_points) == 1  # 新高全清
    assert s_new_high.rows[-1].holding == 0

    s_partial = _simulate(days, 10, 5, 10000, 5000, "partial")
    assert len(s_partial.sell_points) == 1  # 卖一半
    assert s_partial.rows[-1].holding > 0  # 仍留底仓
