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


def test_recycling_return_rate(make_days):
    """资金循环口径：卖出回款复用，收益率分母用峰值占用而非毛买入。

    两轮「跌 15% 买 → 新高全清」：每轮投 10000 @85、卖 @100。
    峰值占用 = 10000（第二轮买入被第一轮回款覆盖，不再新增注资），
    收益率 = 3529/10000 ≈ 35.3%（旧毛口径会把 20000 当分母 → 17.6%，偏低近一半）。
    """
    days = make_days([100, 85, 100, 85, 100])  # 两轮 V 型
    sim = _simulate(days, 10, 5, 10000, 5000, "new_high")
    assert sim.peak_capital == 10000          # 只有一笔净注资，回收资金未被重复计入
    # 绝对盈亏与毛口径恒等：两轮各赚 10000/85*100 - 10000 ≈ 1764.7
    assert round(sim.final_value - sim.peak_capital, 2) == round(2 * (10000 / 85 * 100 - 10000), 2)
    trr = (sim.final_value - sim.peak_capital) / sim.peak_capital * 100
    assert 35 < trr < 36                      # ≈ 35.3%，而非毛口径的 17.6%


def test_reinvest_grows_buys(make_days):
    """复利（净资产高水位）：第二轮买入金额按首轮盈利放大，终值高于不复利。"""
    days = make_days([100, 85, 100, 85, 100])
    s_flat = _simulate(days, 10, 5, 10000, 5000, "new_high", reinvest=False)
    s_comp = _simulate(days, 10, 5, 10000, 5000, "new_high", reinvest=True)

    # 第二轮买入被放大（首轮峰值净资产 11764.7 / 初始 10000 ≈ 1.176 倍）
    assert round(s_comp.buy_points[0]["amount"], 2) == 10000  # 首笔未放大（尚无卖出）
    assert s_comp.buy_points[1]["amount"] > 11000             # 复利后明显放大
    # 峰值占用不变（放大部分由盈利回款覆盖，无需新增注资），终值更高
    assert round(s_comp.peak_capital, 2) == round(s_flat.peak_capital, 2) == 10000
    assert s_comp.final_value > s_flat.final_value


def test_reinvest_noop_without_sells(make_days):
    """sell_mode=none 无卖出 → 复利为空操作，买入金额保持固定。"""
    days = make_days([100, 85, 80])  # 持续下跌触发首笔 + 加仓，但从不卖出
    sim = _simulate(days, 10, 5, 10000, 5000, "none", reinvest=True)
    assert [b["amount"] for b in sim.buy_points] == [10000, 5000]  # 未被放大


def test_reinvest_cash_bounded_no_balloon(make_days):
    """现金约束：密集金字塔下复利不膨胀峰值占用。

    一次深跌多档买入（85→80→75，触发 3 档）期间账户现金耗尽，复利增量被现金封顶 →
    后续档位只投基础金额；峰值占用与「不复利」一致，不会滚出天量占用。
    """
    days = make_days([100, 85, 80, 75, 100])  # 深跌 3 档后回升新高全清
    s_flat = _simulate(days, 10, 5, 10000, 5000, "new_high", reinvest=False)
    s_comp = _simulate(days, 10, 5, 10000, 5000, "new_high", reinvest=True)
    # 峰值占用不因复利膨胀（同非复利）；复利终值 ≥ 非复利
    assert round(s_comp.peak_capital, 2) == round(s_flat.peak_capital, 2)
    assert s_comp.final_value >= s_flat.final_value
