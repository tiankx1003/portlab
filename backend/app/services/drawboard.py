"""基于最大回撤的买入策略看板（015 → 019 v2）。

v2 补齐（相对 v1）：
- ``sell_mode`` 三分支：``none``（只买不卖）/ ``new_high``（新高全清，默认，保留 v1 行为）/ ``partial``（卖一半留底仓）。
- DB 持久化 + task_id 幂等：镜像 MA120，``run_backtest`` 写 calc/result 两表，``make_task_id`` 全参数确定性。
- ``annualized_return``（XIRR）与 ``max_drawdown`` 复用 ``compute.common``（v1 缺）。
- ``benchmark`` 从 ``services.benchmark`` 导入（消除 v1 本地重复定义）。

策略：滚动回撤达 ``threshold`` 首买，每再多跌 ``step`` 加仓（金字塔）；新高（回撤归 0）按 ``sell_mode`` 卖出。
基准 best-effort；数据源随开关（resolve_source），非 akshare 源 task_id 追加后缀。
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..models.drawboard import CalcDrawboardBacktest, ResultDrawboardSummary
from .benchmark import BENCHMARK_SYMBOL, compute_benchmark_returns
from .compute.common import annualized_return, load_prices, max_drawdown
from .fetcher.registry import resolve_source
from .symbol_catalog import lookup_name

_Q2 = Decimal("0.01")  # 金额 2 位
_Q4 = Decimal("0.0001")  # 百分比 / 回撤 4 位
_Q8 = Decimal("0.00000001")  # 份额 8 位

SELL_MODES = ("none", "new_high", "partial")


class ComputeError(Exception):
    """回测计算业务异常。"""


# --------------------------- 行情 + 回撤序列（v1 保留）---------------------------


def get_drawdown_series(
    db: Session, symbol: str, start: date, end: date, source: str | None = None
) -> dict:
    """价格 + 回撤 + 基准序列（图表底图，v1 保留接口）。"""
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


# --------------------------- 仿真核心 ---------------------------


@dataclass
class _DayRow:
    """单日回测明细（落库 + 实时返回共用）。"""

    trade_date: date
    signal: str
    action_amount: float
    holding: float
    cum_invested: float
    cum_proceeds: float
    market_value: float
    pnl: float
    return_rate: float
    drawdown: float  # %
    close: float


@dataclass
class _SimResult:
    rows: list[_DayRow]
    buy_points: list[dict]
    sell_points: list[dict]
    market_values: list[float]
    cashflows: list[tuple[date, float]]
    total_invested: float
    final_value: float


def _simulate(
    days: list[tuple[date, Decimal]],
    threshold_pct: float,
    step_pct: float,
    buy_amount: float,
    add_amount: float,
    sell_mode: str = "new_high",
) -> _SimResult:
    """回撤阈值金字塔买入 + 按 sell_mode 卖出。"""
    t = Decimal(threshold_pct) / Decimal(100) * Decimal(-1)  # 阈值转为负小数
    step = Decimal(step_pct) / Decimal(100)
    a = Decimal(str(buy_amount))
    m = Decimal(str(add_amount))

    running_max = Decimal(0)
    holding = Decimal(0)
    cum_invested = Decimal(0)
    cum_proceeds = Decimal(0)
    last_buy_dd: Decimal | None = None  # 上一笔买入时的回撤（负小数）

    rows: list[_DayRow] = []
    buys: list[dict] = []
    sells: list[dict] = []
    cashflows: list[tuple[date, float]] = []

    for d, price in days:
        if price > running_max:
            running_max = price
        dd = (price / running_max - 1) if running_max > 0 else Decimal(0)  # ≤0

        signal = "hold"
        action_amount = Decimal(0)

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
                action_amount = amt
                signal = "buy"
                buys.append({"date": d, "price": float(price), "amount": float(amt)})
                cashflows.append((d, -float(amt)))

        # 卖出：回撤归 0（新高）且持仓 → 按 sell_mode 处理
        if holding > 0 and dd >= 0:
            if sell_mode == "none":
                pass  # 只买不卖（用户最初设想）
            elif sell_mode == "new_high":
                proceeds = holding * price  # 全清
                cum_proceeds += proceeds
                action_amount = proceeds
                signal = "sell"
                sells.append({"date": d, "price": float(price), "amount": float(proceeds)})
                holding = Decimal(0)
                last_buy_dd = None  # 重置买入阶梯
            elif sell_mode == "partial":
                sell_shares = holding / 2  # 卖一半，留底仓
                proceeds = sell_shares * price
                cum_proceeds += proceeds
                action_amount = proceeds
                signal = "sell"
                sells.append({"date": d, "price": float(price), "amount": float(proceeds)})
                holding -= sell_shares
                # 不重置 last_buy_dd，下次跌破仍可加仓

        mv = holding * price + cum_proceeds
        pnl = mv - cum_invested
        rr = float(pnl / cum_invested * 100) if cum_invested > 0 else 0.0

        rows.append(
            _DayRow(
                trade_date=d,
                signal=signal,
                action_amount=float(action_amount),
                holding=float(holding),
                cum_invested=float(cum_invested),
                cum_proceeds=float(cum_proceeds),
                market_value=float(mv),
                pnl=float(pnl),
                return_rate=rr,
                drawdown=float(dd * 100),
                close=float(price),
            )
        )

    market_values = [r.market_value for r in rows]
    final_value = market_values[-1] if market_values else 0.0
    if rows:
        cashflows.append((rows[-1].trade_date, final_value))

    return _SimResult(
        rows=rows,
        buy_points=buys,
        sell_points=sells,
        market_values=market_values,
        cashflows=cashflows,
        total_invested=float(cum_invested),
        final_value=final_value,
    )


def _build_summary_dict(
    sim: _SimResult, sell_mode: str, dates: list[date]
) -> dict:
    """汇总指标（落库与实时返回共用）。"""
    total_invested = sim.total_invested
    final_value = sim.final_value
    total_pnl = final_value - total_invested
    trr = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    annualized = annualized_return(sim.cashflows, trr, dates)
    mdd = max_drawdown(sim.market_values)
    return {
        "total_invested": round(total_invested, 2),
        "final_value": round(final_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_return_rate": round(trr, 4),
        "annualized_return": round(annualized, 4),
        "max_drawdown": round(mdd, 4),
        "buy_count": len(sim.buy_points),
        "sell_count": len(sim.sell_points),
        "sell_mode": sell_mode,
    }


def _empty_result() -> dict:
    return {
        "dates": [],
        "market_values": [],
        "total_cost": [],
        "pnl": [],
        "return_rates": [],
        "close_prices": [],
        "drawdown": [],
        "holding": [],
        "signals": [],
        "buy_points": [],
        "sell_points": [],
        "benchmark_returns": [],
        "benchmark_name": "",
        "symbol_name": "",
        "summary": {
            "total_invested": 0,
            "final_value": 0,
            "total_pnl": 0,
            "total_return_rate": 0,
            "annualized_return": 0,
            "max_drawdown": 0,
            "buy_count": 0,
            "sell_count": 0,
            "sell_mode": "new_high",
        },
    }


# --------------------------- 实时回测（GET /backtest，无落库）---------------------------


def run_drawdown_backtest(
    db: Session, symbol: str, start: date, end: date,
    threshold: float, step: float, buy_amount: float, add_amount: float,
    sell_mode: str = "new_high", source: str | None = None,
) -> dict:
    """按回撤阈值跑金字塔策略，返回完整 chart 数据 + 汇总（不落库，供实时重算）。"""
    src = source or resolve_source(db)
    days = load_prices(db, symbol, start, end, src)
    if not days:
        return _empty_result()

    sim = _simulate(days, threshold, step, buy_amount, add_amount, sell_mode)
    dates = [r.trade_date for r in sim.rows]
    bench_returns, bench_name = compute_benchmark_returns(db, dates, start, end, source=src)

    return {
        "dates": dates,
        "market_values": [r.market_value for r in sim.rows],
        "total_cost": [r.cum_invested for r in sim.rows],
        "pnl": [r.pnl for r in sim.rows],
        "return_rates": [r.return_rate for r in sim.rows],
        "close_prices": [r.close for r in sim.rows],
        "drawdown": [r.drawdown for r in sim.rows],
        "holding": [r.holding for r in sim.rows],
        "signals": [r.signal for r in sim.rows],
        "buy_points": sim.buy_points,
        "sell_points": sim.sell_points,
        "benchmark_returns": bench_returns,
        "benchmark_name": bench_name,
        "symbol_name": lookup_name(symbol),
        "summary": _build_summary_dict(sim, sell_mode, dates),
    }


# --------------------------- 落库回测（POST /save，task_id 幂等）---------------------------


@dataclass(frozen=True)
class DrawboardParams:
    symbol: str
    start_date: date
    end_date: date
    threshold: float
    step: float
    buy_amount: float
    add_amount: float
    sell_mode: str = "new_high"
    source: str = "akshare"  # 非 akshare 时 task_id 追加后缀，使两源结果互不覆盖


def make_task_id(p: DrawboardParams) -> str:
    """由全部参数确定性生成 task_id，保证幂等。

    默认源（akshare）task_id 不带后缀；非 akshare 源末尾追加 ``_{source}``，
    与 MA120/DCA 一致。
    """
    base = (
        f"db_{p.symbol}_{p.start_date:%Y%m%d}_{p.end_date:%Y%m%d}"
        f"_{p.threshold}_{p.step}_{p.buy_amount}_{p.add_amount}_{p.sell_mode}"
    )
    return f"{base}_{p.source}" if p.source != "akshare" else base


def run_backtest(db: Session, p: DrawboardParams) -> str:
    """执行回测，逐日写入 calc_drawboard_backtest，汇总写入 result_drawboard_summary。返回 task_id。"""
    if p.sell_mode not in SELL_MODES:
        raise ComputeError(f"不支持的卖出方式: {p.sell_mode}")

    days = load_prices(db, p.symbol, p.start_date, p.end_date, p.source)
    if not days:
        raise ComputeError(
            f"标的 {p.symbol} 在 {p.start_date}~{p.end_date} 无行情数据，请先拉取数据"
        )

    task_id = make_task_id(p)
    sim = _simulate(days, p.threshold, p.step, p.buy_amount, p.add_amount, p.sell_mode)
    dates = [r.trade_date for r in sim.rows]

    calc_rows = [
        CalcDrawboardBacktest(
            task_id=task_id,
            trade_date=r.trade_date,
            signal=r.signal,
            action_amount=Decimal(str(r.action_amount)).quantize(_Q2),
            holding=Decimal(str(r.holding)).quantize(_Q8),
            cum_invested=Decimal(str(r.cum_invested)).quantize(_Q2),
            cum_proceeds=Decimal(str(r.cum_proceeds)).quantize(_Q2),
            market_value=Decimal(str(r.market_value)).quantize(_Q2),
            pnl=Decimal(str(r.pnl)).quantize(_Q2),
            return_rate=Decimal(str(r.return_rate)).quantize(_Q4),
            drawdown=Decimal(str(r.drawdown)).quantize(_Q4),
            close=Decimal(str(r.close)).quantize(_Q4),
        )
        for r in sim.rows
    ]
    summary = _build_summary_orm(task_id, p, sim, dates)
    _write_results(db, task_id, calc_rows, summary)
    return task_id


def _build_summary_orm(
    task_id: str, p: DrawboardParams, sim: _SimResult, dates: list[date]
) -> ResultDrawboardSummary:
    s = _build_summary_dict(sim, p.sell_mode, dates)
    return ResultDrawboardSummary(
        task_id=task_id,
        symbol=p.symbol,
        sell_mode=p.sell_mode,
        threshold=Decimal(str(p.threshold)).quantize(_Q4),
        step=Decimal(str(p.step)).quantize(_Q4),
        buy_amount=Decimal(str(p.buy_amount)).quantize(_Q2),
        add_amount=Decimal(str(p.add_amount)).quantize(_Q2),
        start_date=p.start_date,
        end_date=p.end_date,
        total_invested=Decimal(str(s["total_invested"])).quantize(_Q2),
        final_value=Decimal(str(s["final_value"])).quantize(_Q2),
        total_pnl=Decimal(str(s["total_pnl"])).quantize(_Q2),
        total_return_rate=Decimal(str(s["total_return_rate"])).quantize(_Q4),
        annualized_return=Decimal(str(s["annualized_return"])).quantize(_Q4),
        max_drawdown=Decimal(str(s["max_drawdown"])).quantize(_Q4),
        buy_count=s["buy_count"],
        sell_count=s["sell_count"],
    )


def _write_results(
    db: Session,
    task_id: str,
    calc_rows: list[CalcDrawboardBacktest],
    summary: ResultDrawboardSummary,
) -> None:
    db.execute(delete(CalcDrawboardBacktest).where(CalcDrawboardBacktest.task_id == task_id))
    db.execute(delete(ResultDrawboardSummary).where(ResultDrawboardSummary.task_id == task_id))
    db.add_all(calc_rows)
    db.add(summary)
    db.commit()


# --------------------------- DB 读取（GET /{task_id}/chart|summary）---------------------------


def load_chart_rows(db: Session, task_id: str) -> list[CalcDrawboardBacktest]:
    return (
        db.execute(
            select(CalcDrawboardBacktest)
            .where(CalcDrawboardBacktest.task_id == task_id)
            .order_by(CalcDrawboardBacktest.trade_date)
        )
        .scalars()
        .all()
    )
