"""契约表解析单测：覆盖 docs/api-registry.yaml。"""

from pathlib import Path

from portlab_mcp.registry_loader import check_drift, group_map, load_registry

REGISTRY = Path(__file__).resolve().parents[2] / "docs" / "api-registry.yaml"


def test_registry_loads_32_exposed():
    specs = load_registry(REGISTRY)
    assert len(specs) == 32, f"期望 32 个 expose=true，实际 {len(specs)}"


def test_all_exposed_have_required_fields():
    for s in load_registry(REGISTRY):
        assert s.tool_name, f"{s} 缺 tool_name"
        assert s.group in {"system", "market", "backtest", "drawboard", "event", "arena"}, s
        assert s.sample in {"none", "chart80", "event_impact"}, s
        assert s.method in {"GET", "POST"}, s


def test_expected_tools_present():
    names = {s.tool_name for s in load_registry(REGISTRY)}
    expected = {
        "health_check",
        "get_roadmap",
        "get_release_notes",
        "get_recent_backtests",
        "search_symbols",
        "get_market_overview",
        "get_etf_flow",
        "get_valuation_indices",
        "get_valuation_single",
        "get_valuation_overlay",
        "run_dca_backtest",
        "run_ma120_backtest",
        "run_grid_backtest",
        "run_portfolio_backtest",
        "save_drawboard_backtest",
        "get_dca_chart",
        "get_dca_summary",
        "get_ma120_chart",
        "get_ma120_summary",
        "get_grid_chart",
        "get_grid_summary",
        "get_portfolio_chart",
        "get_portfolio_summary",
        "get_drawboard_chart",
        "get_drawboard_summary",
        "get_drawboard_series",
        "run_drawboard_realtime",
        "get_event_themes",
        "get_event_theme_detail",
        "get_event_detail",
        "get_event_impact",
        "compare_strategies",
    }
    assert names == expected, f"缺/多：{expected ^ names}"


def test_hidden_not_loaded():
    """敏感/写/preview/feedback/旧 valuation 不应出现在暴露清单。"""
    names = {s.tool_name for s in load_registry(REGISTRY)}
    for hidden in (
        "data_fetch",
        "datasource_status",
        "event_smart_match",
        "feedback",
        "valuation_legacy",
    ):
        assert hidden not in names


def test_group_map_and_drift():
    specs = load_registry(REGISTRY)
    gm = group_map(specs)
    assert gm["run_ma120_backtest"] == "backtest"
    assert gm["get_valuation_single"] == "market"
    assert gm["compare_strategies"] == "arena"
    # 完全对齐 → 无漂移
    assert check_drift(specs, {s.tool_name for s in specs}) == []
    # 缺一个 → 报告漂移
    missing = {s.tool_name for s in specs} - {"health_check"}
    warns = check_drift(specs, missing)
    assert any("health_check" in w for w in warns)
