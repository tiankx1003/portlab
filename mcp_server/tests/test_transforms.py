"""降采样逻辑单测：覆盖 backend 全部 chart 形状。"""

from portlab_mcp.transforms import apply_sample, downsample_chart


def _make_chart(n=2500, signals=()):
    """构造一个 dates + 三条等长标量曲线 + buy/sell_points 的典型回测图。

    dates 用纯数字串作 token，便于 signal_dates 直接引用（如 "499"）。
    """
    dates = [str(i) for i in range(n)]
    return {
        "dates": dates,
        "nav": [round(1 + i * 0.001, 4) for i in range(n)],
        "drawdown": [round(-i * 0.0001, 4) for i in range(n)],
        "cost": [1.0] * n,
        "buy_points": [{"date": d, "price": 10.0} for d in signals],
        "sell_points": [],
    }


def test_no_sampling_when_short():
    chart = _make_chart(n=50)
    out = downsample_chart(chart, 80)
    assert out == chart  # n <= target：内容原样返回（返回的是等值副本）
    assert "_meta" not in out


def test_downsample_caps_points_and_keeps_ends():
    chart = _make_chart(n=2500)
    out = downsample_chart(chart, 80)
    meta = out["_meta"]
    assert meta["original_len"] == 2500
    assert meta["sampled_len"] <= 80
    # 首尾保留
    assert out["dates"][0] == chart["dates"][0]
    assert out["dates"][-1] == chart["dates"][-1]
    # 所有并列数组同长（索引集一致）
    assert len(out["nav"]) == len(out["dates"]) == len(out["drawdown"]) == len(out["cost"])


def test_signal_days_preserved():
    chart = _make_chart(n=2500, signals=("499", "1999"))
    out = downsample_chart(chart, 80)
    assert "499" in out["dates"]
    assert "1999" in out["dates"]
    # 买卖点对象本身不降采样
    assert out["buy_points"] == chart["buy_points"]


def test_nested_objects_not_downsampled():
    """portfolio chart：correlation_matrix / frontier 不动；nav/drawdown/benchmark_nav 切片。"""
    n = 500
    chart = {
        "dates": list(range(n)),
        "nav": [1.0] * n,
        "drawdown": [0.0] * n,
        "benchmark_nav": [1.0] * n,
        "correlation_symbols": ["a", "b"],
        "correlation_matrix": [[1.0, 0.5], [0.5, 1.0]],
        "frontier": {"volatilities": [0.1, 0.2], "returns": [0.05, 0.1]},
    }
    out = downsample_chart(chart, 80)
    assert len(out["nav"]) <= 80
    assert out["correlation_matrix"] == chart["correlation_matrix"]  # 矩阵原样
    assert out["frontier"] == chart["frontier"]  # 前沿原样
    assert out["correlation_symbols"] == ["a", "b"]  # 元数据不动


def test_overlay_series_synced():
    """overlay：顶层 dates 与各 series[].normalized 用同一索引集切片。"""
    n = 300
    chart = {
        "dates": list(range(n)),
        "series": [
            {"index_code": "000300", "name_cn": "沪深300", "normalized": [1.0] * n},
            {"index_code": "000922", "name_cn": "红利", "normalized": [2.0] * n},
        ],
        "base": 1,
    }
    out = downsample_chart(chart, 80)
    assert out["_meta"]["sampled_len"] <= 80
    for item in out["series"]:
        assert len(item["normalized"]) == len(out["dates"])  # 与 dates 同长
        assert item["index_code"] in ("000300", "000922")  # 非数组字段不动


def test_arena_nav_series_per_entry():
    """arena：nav_series 每项按各自 dates 降采样。"""
    chart = {
        "items": [{"task_id": "t1"}],
        "nav_series": {
            "t1": {"dates": list(range(300)), "nav": [1.0] * 300},
            "t2": {"dates": list(range(400)), "nav": [2.0] * 400},
        },
    }
    out = downsample_chart(chart, 80)
    assert len(out["nav_series"]["t1"]["nav"]) <= 80
    assert len(out["nav_series"]["t2"]["nav"]) <= 80
    assert out["items"] == chart["items"]  # 元数据不动


def test_event_impact_window_returns_and_benchmark():
    """event impact：window_returns + benchmark_series 按各自 dates 降采样；矩阵/排行不动。"""
    chart = {
        "event_id": 1,
        "window_returns": {
            "510880": {"dates": list(range(200)), "returns": [0.0] * 200},
            "000300": {"dates": list(range(200)), "returns": [0.0] * 200},
        },
        "benchmark_series": {"dates": list(range(200)), "returns": [0.0] * 200},
        "ranking": [{"symbol": "510880", "change_pct": 1.2}],
        "correlation_matrix": [[1.0, 0.3], [0.3, 1.0]],
    }
    out = apply_sample(chart, "event_impact", 80)
    assert len(out["window_returns"]["510880"]["returns"]) <= 80
    assert len(out["benchmark_series"]["returns"]) <= 80
    assert out["ranking"] == chart["ranking"]
    assert out["correlation_matrix"] == chart["correlation_matrix"]


def test_drawboard_series_benchmark_group():
    """drawboard series：标的组(dates)与基准组(benchmark_dates)各自降采样。"""
    n, nb = 300, 280
    chart = {
        "dates": list(range(n)),
        "prices": [10.0] * n,
        "drawdown": [0.0] * n,
        "benchmark_dates": list(range(nb)),
        "benchmark_pct": [1.0] * nb,
    }
    out = downsample_chart(chart, 80)
    assert len(out["prices"]) <= 80
    assert len(out["benchmark_pct"]) <= 80
    assert len(out["benchmark_dates"]) == len(out["benchmark_pct"])


def test_apply_sample_dispatch():
    assert apply_sample({"x": 1}, "none") == {"x": 1}
    assert apply_sample(None, "chart80") is None
    chart = _make_chart(n=300)
    assert "_meta" in apply_sample(chart, "chart80", 80)
    assert "_meta" in apply_sample(chart, "event_impact", 80)
