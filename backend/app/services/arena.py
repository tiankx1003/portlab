"""策略擂台（023）—— 跨策略/跨标的横向对比。

纯消费现有 ``result_*_summary`` / ``calc_*_backtest`` 四组表，无新引擎、无新表。
- ``list_strategy_results``：跨四张 summary 表查询 + 字段统一映射为 StrategyResultItem。
- ``get_normalized_nav``：读 calc 表 market_value 归一化到起点=100，供多曲线叠加对比。

缺表（某策略未实现/无数据）优雅跳过，不报错。
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.calc import CalcDcaBacktest, CalcMa120Backtest
from ..models.drawboard import CalcDrawboardBacktest, ResultDrawboardSummary
from ..models.grid import CalcGridBacktest, ResultGridSummary
from ..models.result import ResultDcaSummary, ResultMa120Summary
from ..services.symbol_catalog import lookup_name

SUMMARY_TABLES = {
    "dca": ResultDcaSummary,
    "ma120": ResultMa120Summary,
    "drawboard": ResultDrawboardSummary,
    "grid": ResultGridSummary,
}
CALC_TABLES = {
    "dca": CalcDcaBacktest,
    "ma120": CalcMa120Backtest,
    "drawboard": CalcDrawboardBacktest,
    "grid": CalcGridBacktest,
}


def normalize_to_100(values: list[float]) -> list[float]:
    """归一化到起点=100（便于不同策略/标的净值叠加对比）。"""
    if not values:
        return []
    base = values[0] if values[0] != 0 else 1.0
    return [v / base * 100 for v in values]


def _freq_cn(freq: str) -> str:
    return {"weekly": "每周", "monthly": "每月"}.get(freq, freq)


def _map_item(strategy: str, r) -> dict:
    """把某 summary 行统一映射为 StrategyResultItem dict（各策略特有字段降级为 params_summary）。"""
    common = dict(
        task_id=r.task_id,
        strategy=strategy,
        symbol=r.symbol,
        symbol_name=lookup_name(r.symbol),
        start_date=r.start_date,
        end_date=r.end_date,
        total_return_rate=float(r.total_return_rate),
        annualized_return=float(r.annualized_return),
        max_drawdown=float(r.max_drawdown),
        sharpe=None,
    )
    if strategy == "dca":
        common.update(
            buy_count=int(r.invest_count),
            sell_count=0,
            params_summary=f"{_freq_cn(r.frequency)}{float(r.amount):.0f}元",
        )
    elif strategy == "ma120":
        common.update(
            buy_count=int(r.buy_count),
            sell_count=int(r.sell_count),
            params_summary=f"阈值{float(r.buy_threshold):.3f} 步长{float(r.step):.2f} {r.sell_mode}",
        )
    elif strategy == "drawboard":
        common.update(
            buy_count=int(r.buy_count),
            sell_count=int(r.sell_count),
            params_summary=(
                f"阈值{float(r.threshold):.0f}% 步长{float(r.step):.0f}% {r.sell_mode}"
            ),
        )
    elif strategy == "grid":
        common.update(
            buy_count=int(r.buy_count),
            sell_count=int(r.sell_count),
            params_summary=(
                f"中枢{float(r.center_price):.2f} 间距{float(r.step_pct):.0f}% "
                f"{r.n_levels_above}×{r.n_levels_below}"
            ),
        )
    return common


def list_strategy_results(
    db: Session,
    mode: str,
    symbol: str | None = None,
    strategy: str | None = None,
    symbols: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[dict]:
    """跨策略（固定 symbol）或跨标的（固定 strategy）查询，返回统一结构对比项。"""
    items: list[dict] = []
    if mode == "cross_strategy":
        for strat, model in SUMMARY_TABLES.items():
            try:
                rows = db.execute(select(model).where(model.symbol == symbol)).scalars().all()
            except Exception:  # noqa: BLE001 - 缺表优雅跳过
                continue
            items.extend(_map_item(strat, r) for r in rows)
    else:  # cross_symbol
        model = SUMMARY_TABLES.get(strategy or "")
        if model:
            q = select(model)
            if symbols:
                q = q.where(model.symbol.in_(symbols))
            rows = db.execute(q).scalars().all()
            items.extend(_map_item(strategy, r) for r in rows)

    if start:
        items = [i for i in items if i["end_date"] >= start]
    if end:
        items = [i for i in items if i["start_date"] <= end]
    return items


def get_normalized_nav(
    db: Session, task_id: str, strategy: str
) -> tuple[list[date], list[float]]:
    """读对应 calc 表 market_value，归一化到起点=100。"""
    model = CALC_TABLES.get(strategy)
    if not model:
        return [], []
    rows = db.execute(
        select(model.trade_date, model.market_value)
        .where(model.task_id == task_id)
        .order_by(model.trade_date)
    ).all()
    dates = [r.trade_date for r in rows]
    nav = normalize_to_100([float(r.market_value) for r in rows])
    return dates, nav
