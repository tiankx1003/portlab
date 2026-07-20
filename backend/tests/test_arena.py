"""策略擂台（023）单测 —— 纯函数 normalize_to_100 / _map_item / _freq_cn。

跨表查询（list_strategy_results）依赖 DB，靠 UI 截图端到端验证。
"""

from types import SimpleNamespace

from app.services.arena import _freq_cn, _map_item, normalize_to_100


def test_normalize_to_100_starts_at_100():
    out = normalize_to_100([1.0, 1.2, 0.9, 1.5])
    assert abs(out[0] - 100) < 1e-9
    assert abs(out[1] - 120) < 1e-6
    assert abs(out[3] - 150) < 1e-6


def test_normalize_empty():
    assert normalize_to_100([]) == []


def test_freq_cn():
    assert _freq_cn("monthly") == "每月"
    assert _freq_cn("weekly") == "每周"
    assert _freq_cn("daily") == "daily"


def test_map_item_dca():
    row = SimpleNamespace(
        task_id="dca_510880_x", symbol="510880", frequency="monthly", amount=1000,
        start_date=__import__("datetime").date(2022, 1, 1),
        end_date=__import__("datetime").date(2024, 1, 1),
        total_return_rate=12.3, annualized_return=4.0, max_drawdown=15.0, invest_count=24,
    )
    item = _map_item("dca", row)
    assert item["strategy"] == "dca"
    assert item["buy_count"] == 24
    assert item["sell_count"] == 0
    assert item["sharpe"] is None
    assert "每月" in item["params_summary"]


def test_map_item_grid():
    row = SimpleNamespace(
        task_id="grid_x", symbol="510300", center_price=4.0, step_pct=3,
        n_levels_above=5, n_levels_below=5,
        start_date=__import__("datetime").date(2022, 1, 1),
        end_date=__import__("datetime").date(2024, 1, 1),
        total_return_rate=20.0, annualized_return=9.0, max_drawdown=8.0,
        buy_count=80, sell_count=78,
    )
    item = _map_item("grid", row)
    assert item["buy_count"] == 80
    assert "中枢4.00" in item["params_summary"]
    assert "5×5" in item["params_summary"]
