"""基于最大回撤的买入策略看板（015）。

- ``get_drawdown_series``：价格（含起算至今累计涨幅%）+ 滚动最大回撤%（取负）+ 基准（510300），
  供前端「左轴 0 线镜像」画价格 / 回撤。
- ``run_drawdown_backtest``：金字塔分批买入（回撤达阈值首买，每再多跌 step 加仓），
  新高（回撤归 0）清仓兑现；返回买/卖点、市值、收益率序列与汇总。

数据源随开关（resolve_source）；基准 best-effort，无数据则空。
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from .compute.common import load_prices
from .fetcher.registry import resolve_source

BENCHMARK_SYMBOL = "510300"


def get_drawdown_series(
    db: Session, symbol: str, start: date, end: date, source: str | None = None
) -> dict:
    """价格 + 回撤 + 基准序列。"""
    src = source or resolve_source(db)
    days = load_prices(db, symbol, start, end, src)
    bench = load_prices(db, BENCHMARK_SYMBOL, start, end, src)

    dates: list[date] = []
    prices: list[float] = []
    price_pct: list[float | None] = []  # 起算至今累计涨幅 %
    drawdown: list[float | None] = []  # 滚动最大回撤 %（≤0）
    running_max = Decimal(0)
    base = days[0][1] if days else None
    for d, c in days:
        if c > running_max:
            running_max = c
        dates.append(d)
        prices.append(float(c))
        price_pct.append(float((c / base - 1) * 100) if base else None)
        drawdown.append(float((c / running_max - 1) * 100) if running_max > 0 else 0.0)

    bench_dates = [d for d, _ in bench]
    bench_pct: list[float | None] = []
    bbase = bench[0][1] if bench else None
    for _, c in bench:
        bench_pct.append(float((c / bbase - 1) * 100) if bbase else None)

    return {
        "dates": dates,
        "prices": prices,
        "price_pct": price_pct,
        "drawdown": drawdown,
        "benchmark_dates": bench_dates,
        "benchmark_pct": bench_pct,
    }


@dataclass
class _SimResult:
    dates: list[date]
    market_values: list[float]
    return_rates: list[float]
    buy_points: list[dict]
    sell_points: list[dict]
    total_invested: float
    final_value: float


def _simulate(
    days: list[tuple[date, Decimal]], threshold_pct: float, step_pct: float,
    buy_amount: float, add_amount: float,
) -> _SimResult:
    """回撤阈值金字塔买入 + 新高清仓。"""
    t = Decimal(threshold_pct) / Decimal(100) * Decimal(-1)  # 阈值转为负小数
    step = Decimal(step_pct) / Decimal(100)
    a = Decimal(str(buy_amount))
    m = Decimal(str(add_amount))

    running_max = Decimal(0)
    holding = Decimal(0)
    cum_invested = Decimal(0)
    cum_proceeds = Decimal(0)
    last_buy_dd: Decimal | None = None  # 上一笔买入时的回撤（负小数）

    dates: list[date] = []
    mvs: list[float] = []
    rrs: list[float] = []
    buys: list[dict] = []
    sells: list[dict] = []

    for d, price in days:
        if price > running_max:
            running_max = price
        dd = (price / running_max - 1) if running_max > 0 else Decimal(0)  # ≤0

        # 买入：首次达阈值 / 较上次买入再跌 step
        if (last_buy_dd is None and dd <= t) or (
            last_buy_dd is not None and dd <= last_buy_dd - step
        ):
            amt = a if last_buy_dd is None else m
            if amt > 0:
                shares = amt / price
                holding += shares
                cum_invested += amt
                last_buy_dd = dd
                buys.append({"date": d, "price": float(price), "amount": float(amt)})

        # 卖出：回撤归 0（新高）且持仓 → 清仓兑现
        if holding > 0 and dd >= 0:
            proceeds = (holding * price)
            cum_proceeds += proceeds
            sells.append({"date": d, "price": float(price), "amount": float(proceeds)})
            holding = Decimal(0)
            last_buy_dd = None

        mv = holding * price + cum_proceeds
        rr = float((mv - cum_invested) / cum_invested * 100) if cum_invested > 0 else 0.0
        dates.append(d)
        mvs.append(float(mv))
        rrs.append(rr)

    return _SimResult(
        dates=dates, market_values=mvs, return_rates=rrs,
        buy_points=buys, sell_points=sells,
        total_invested=float(cum_invested),
        final_value=mvs[-1] if mvs else 0.0,
    )


def run_drawdown_backtest(
    db: Session, symbol: str, start: date, end: date,
    threshold: float, step: float, buy_amount: float, add_amount: float,
    source: str | None = None,
) -> dict:
    """按回撤阈值跑金字塔策略，返回买/卖点、市值、收益率序列与汇总。"""
    src = source or resolve_source(db)
    days = load_prices(db, symbol, start, end, src)
    if not days:
        return {
            "dates": [], "market_values": [], "return_rates": [],
            "buy_points": [], "sell_points": [],
            "summary": {"total_invested": 0, "final_value": 0, "total_pnl": 0,
                        "total_return_rate": 0, "buy_count": 0, "sell_count": 0},
        }
    sim = _simulate(days, threshold, step, buy_amount, add_amount)
    total_pnl = sim.final_value - sim.total_invested
    trr = (total_pnl / sim.total_invested * 100) if sim.total_invested > 0 else 0.0
    return {
        "dates": sim.dates,
        "market_values": sim.market_values,
        "return_rates": sim.return_rates,
        "buy_points": sim.buy_points,
        "sell_points": sim.sell_points,
        "summary": {
            "total_invested": round(sim.total_invested, 2),
            "final_value": round(sim.final_value, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_rate": round(trr, 4),
            "buy_count": len(sim.buy_points),
            "sell_count": len(sim.sell_points),
        },
    }
