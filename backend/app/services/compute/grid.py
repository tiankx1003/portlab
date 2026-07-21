"""网格交易策略回测计算引擎（020）。

策略：用户设定**中枢价** + **网格间距 step_pct%** + **每格资金 M**，自动生成上下网格线。
- 价格**跌穿**某网格线 → 买入一格（M 元）。
- 价格**涨破**某网格线 → 卖出一格（FIFO 卖出最早买入份额，锁定差价）。
- 循环套利，吃箱体震荡。bound_mode：hold（突破等回归）/ stop（止损止盈清仓）/ reset（重置中枢）。

核心算法：逐日比较 close 与 prev_close，统计被穿越的网格线数——
- 下跌（close<prev_close）：线 ln 满足 close<=ln<prev_close 即跌穿 → 每条买入一格（跨多格多次买）。
- 上涨（close>prev_close）：线 ln 满足 prev_close<ln<=close 即涨破 → 每条卖出一格（FIFO）。

grid_profit = 累计已实现差价（卖出回款 − 对应买入成本，FIFO 配对）；cycle_count = 配对次数。
仿真核心 ``_simulate_grid`` 为纯函数（输入行情序列，输出结果对象），不依赖 DB，便于单测。
金额/份额用 Decimal；年化与回撤转 float。task_id 全参数确定性，重复执行幂等（先删后写）。
"""

from collections import deque
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_FLOOR, Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...models.grid import CalcGridBacktest, ResultGridSummary
from .common import annualized_return, load_prices, max_drawdown
from ..benchmark import compute_benchmark_returns
from ..symbol_catalog import lookup_name

_Q2 = Decimal("0.01")  # 金额 2 位
_Q4 = Decimal("0.0001")  # 百分比 4 位
_Q8 = Decimal("0.00000001")  # 份额 8 位

BOUND_MODES = ("hold", "stop", "reset")


class ComputeError(Exception):
    """回测计算业务异常。"""


# --------------------------- 网格生成（纯函数）---------------------------


def build_grid_levels(
    center: Decimal, step_pct: Decimal, n_above: int, n_below: int
) -> list[Decimal]:
    """以 center 为中枢、step_pct% 为间距生成上下网格价（升序返回，不含中枢本身）。

    上方 n_above 格：center×(1+step), center×(1+2step), ...；下方 n_below 格对称。
    """
    step = step_pct / Decimal(100)
    levels: list[Decimal] = [
        center * (Decimal(1) + step * Decimal(k)) for k in range(1, n_above + 1)
    ]
    levels += [center * (Decimal(1) - step * Decimal(k)) for k in range(1, n_below + 1)]
    return sorted(levels)


def _grid_index(close: Decimal, center: Decimal, step: Decimal) -> int:
    """close 相对中枢所在的格序号（中枢=0，上方正、下方负；突破时可超出 ±n）。

    grid_index = floor((close/center − 1) / step)。
    """
    if center > 0 and step > 0:
        ratio = close / center - Decimal(1)
        return int((ratio / step).to_integral_value(rounding=ROUND_FLOOR))
    return 0


# --------------------------- 仿真核心（纯函数）---------------------------


@dataclass
class _GridDayRow:
    trade_date: date
    signal: str
    action_amount: float
    holding: float
    cash_balance: float
    cum_invested: float
    cum_proceeds: float
    market_value: float
    pnl: float
    return_rate: float
    close: float
    grid_index: int


@dataclass
class _GridSimResult:
    rows: list[_GridDayRow]
    buy_points: list[dict]
    sell_points: list[dict]
    market_values: list[float]
    cashflows: list[tuple[date, float]]
    total_invested: float
    final_value: float
    grid_profit: float
    cycle_count: int


def _simulate_grid(
    days: list[tuple[date, Decimal]],
    center: Decimal,
    step_pct: Decimal,
    amount: Decimal,
    n_above: int,
    n_below: int,
    bound_mode: str = "hold",
) -> _GridSimResult:
    """网格双向触发仿真（纯函数，不依赖 DB）。"""
    step = step_pct / Decimal(100)
    lines = build_grid_levels(center, step_pct, n_above, n_below)  # 升序网格线
    m = amount

    holding = Decimal(0)
    cum_invested = Decimal(0)
    cum_proceeds = Decimal(0)
    grid_profit = Decimal(0)
    cycle_count = 0
    lots: deque[tuple[Decimal, Decimal]] = deque()  # FIFO：(买入价, 份额)

    prev_close = center  # 首日视为从中枢起算
    rows: list[_GridDayRow] = []
    buys: list[dict] = []
    sells: list[dict] = []
    cashflows: list[tuple[date, float]] = []

    def _liquidate(d: date, close: Decimal, reason: str) -> None:
        """bound_mode=stop：清仓所有剩余持仓（止损/止盈），FIFO 配对计入 grid_profit。"""
        nonlocal holding, cum_proceeds, grid_profit, cycle_count
        if holding <= 0 or not lots:
            return
        proceeds = (holding * close).quantize(_Q2)
        cost = Decimal(0)
        for bp, sh in lots:
            cost += sh * bp
        grid_profit += proceeds - cost
        cum_proceeds += proceeds
        holding = Decimal(0)
        lots.clear()
        cycle_count += 1  # 一次清仓计为一次了结
        sells.append(
            {"date": d, "price": float(close), "amount": float(proceeds), "reason": reason}
        )

    for d, close in days:
        signal = "hold"
        action_amount = Decimal(0)

        if close < prev_close:
            # 下跌：跌穿的线（close <= ln < prev_close）每条买入一格
            for ln in lines:
                if close <= ln < prev_close:
                    shares = m / close
                    holding += shares
                    cum_invested += m
                    lots.append((close, shares))
                    action_amount += m
                    signal = "buy"
                    buys.append({"date": d, "price": float(close), "amount": float(m)})
                    cashflows.append((d, -float(m)))
        elif close > prev_close:
            # 上涨：涨破的线（prev_close < ln <= close）每条卖出一格（FIFO）
            for ln in lines:
                if prev_close < ln <= close and lots:
                    buy_price, shares = lots.popleft()
                    proceeds = (shares * close).quantize(_Q2)
                    cost = (shares * buy_price).quantize(_Q2)
                    grid_profit += proceeds - cost
                    cum_proceeds += proceeds
                    holding -= shares
                    action_amount += proceeds
                    signal = "sell"
                    cycle_count += 1
                    sells.append({"date": d, "price": float(close), "amount": float(proceeds)})

        # bound_mode 突破处理（在穿越触发之后）
        if bound_mode == "stop":
            if close < lines[0] and prev_close >= lines[0]:
                _liquidate(d, close, "止损")  # 跌破下沿止损清仓
                if signal == "hold":
                    signal = "sell"
            elif close > lines[-1] and prev_close <= lines[-1]:
                _liquidate(d, close, "止盈")  # 突破上沿止盈清仓
                if signal == "hold":
                    signal = "sell"
        elif bound_mode == "reset":
            # 突破任一外沿 → 以新价格为中枢重置网格（持仓保留）
            if close < lines[0] or close > lines[-1]:
                center = close
                lines = build_grid_levels(center, step_pct, n_above, n_below)

        cash_balance = cum_proceeds - cum_invested
        mv = (holding * close + cum_proceeds).quantize(_Q2)
        pnl = (mv - cum_invested).quantize(_Q2)
        rr = float(pnl / cum_invested * 100) if cum_invested > 0 else 0.0

        rows.append(
            _GridDayRow(
                trade_date=d,
                signal=signal,
                action_amount=float(action_amount),
                holding=float(holding),
                cash_balance=float(cash_balance),
                cum_invested=float(cum_invested),
                cum_proceeds=float(cum_proceeds),
                market_value=float(mv),
                pnl=float(pnl),
                return_rate=rr,
                close=float(close),
                grid_index=_grid_index(close, center, step),
            )
        )
        prev_close = close

    market_values = [r.market_value for r in rows]
    final_value = market_values[-1] if market_values else 0.0
    if rows:
        cashflows.append((rows[-1].trade_date, final_value))

    return _GridSimResult(
        rows=rows,
        buy_points=buys,
        sell_points=sells,
        market_values=market_values,
        cashflows=cashflows,
        total_invested=float(cum_invested),
        final_value=final_value,
        grid_profit=float(grid_profit),
        cycle_count=cycle_count,
    )


# --------------------------- 落库回测（POST，task_id 幂等）---------------------------


@dataclass(frozen=True)
class GridParams:
    symbol: str
    start_date: date
    end_date: date
    center_price: Decimal
    step_pct: Decimal  # 百分数，如 Decimal("3") = 3%
    amount_per_level: Decimal
    n_levels_above: int = 5
    n_levels_below: int = 5
    bound_mode: str = "hold"  # hold/stop/reset
    source: str = "akshare"


def make_task_id(p: GridParams) -> str:
    """全参数确定性 task_id；非 akshare 源末尾追加 ``_{source}``。"""
    base = (
        f"grid_{p.symbol}_{p.start_date:%Y%m%d}_{p.end_date:%Y%m%d}"
        f"_{p.center_price}_{p.step_pct}_{p.amount_per_level}"
        f"_{p.n_levels_above}_{p.n_levels_below}_{p.bound_mode}"
    )
    return f"{base}_{p.source}" if p.source != "akshare" else base


def _compute(db: Session, p: GridParams):
    """校验 + 加载行情 + 仿真 + 汇总（不落库）。返回 (task_id, sim, summary)。"""
    if p.bound_mode not in BOUND_MODES:
        raise ComputeError(f"不支持的突破处理: {p.bound_mode}（可选 hold/stop/reset）")
    if p.center_price <= 0 or p.step_pct <= 0 or p.amount_per_level <= 0:
        raise ComputeError("center_price / step_pct / amount_per_level 必须 > 0")
    if not (1 <= p.n_levels_above <= 20 and 1 <= p.n_levels_below <= 20):
        raise ComputeError("n_levels_above / n_levels_below 须在 1~20")

    days = load_prices(db, p.symbol, p.start_date, p.end_date, p.source)
    if not days:
        raise ComputeError(
            f"标的 {p.symbol} 在 {p.start_date}~{p.end_date} 无行情数据，请先拉取数据"
        )

    task_id = make_task_id(p)
    sim = _simulate_grid(
        days, p.center_price, p.step_pct, p.amount_per_level,
        p.n_levels_above, p.n_levels_below, p.bound_mode,
    )
    dates = [r.trade_date for r in sim.rows]
    summary = _build_summary_orm(task_id, p, sim, dates)
    return task_id, sim, summary


def run_backtest(db: Session, p: GridParams) -> str:
    """执行回测并落库（calc + result 两表，幂等先删后写）。返回 task_id。"""
    task_id, sim, summary = _compute(db, p)
    calc_rows = [
        CalcGridBacktest(
            task_id=task_id,
            trade_date=r.trade_date,
            signal=r.signal,
            action_amount=Decimal(str(r.action_amount)).quantize(_Q2),
            holding_shares=Decimal(str(r.holding)).quantize(_Q8),
            cash_balance=Decimal(str(r.cash_balance)).quantize(_Q2),
            cum_invested=Decimal(str(r.cum_invested)).quantize(_Q2),
            cum_proceeds=Decimal(str(r.cum_proceeds)).quantize(_Q2),
            market_value=Decimal(str(r.market_value)).quantize(_Q2),
            pnl=Decimal(str(r.pnl)).quantize(_Q2),
            return_rate=Decimal(str(r.return_rate)).quantize(_Q4),
            close=Decimal(str(r.close)).quantize(_Q4),
            grid_index=r.grid_index,
        )
        for r in sim.rows
    ]
    _write_results(db, task_id, calc_rows, summary)
    return task_id


def run_realtime(db: Session, p: GridParams) -> dict:
    """实时回测（不落库）：返回 chart 数据 + summary，供「开始回测」预览。"""
    task_id, sim, summary = _compute(db, p)
    trade_dates = [r.trade_date for r in sim.rows]
    benchmark_returns, benchmark_name = compute_benchmark_returns(
        db, trade_dates, p.start_date, p.end_date, source=p.source
    )
    name = lookup_name(p.symbol)
    grid_levels = [
        float(x) for x in build_grid_levels(
            p.center_price, p.step_pct, p.n_levels_above, p.n_levels_below
        )
    ]
    buy_points: list[dict] = []
    sell_points: list[dict] = []
    for r in sim.rows:
        if r.signal == "buy":
            buy_points.append({"date": r.trade_date, "price": float(r.close), "amount": float(r.action_amount)})
        elif r.signal == "sell":
            sell_points.append({"date": r.trade_date, "price": float(r.close), "amount": float(r.action_amount)})
    return {
        "dates": trade_dates,
        "close_prices": [float(r.close) for r in sim.rows],
        "market_values": [float(r.market_value) for r in sim.rows],
        "total_cost": [float(r.cum_invested) for r in sim.rows],
        "pnl": [float(r.pnl) for r in sim.rows],
        "return_rates": [float(r.return_rate) for r in sim.rows],
        "holding": [float(r.holding) for r in sim.rows],
        "signals": [r.signal for r in sim.rows],
        "grid_levels": grid_levels,
        "buy_points": buy_points,
        "sell_points": sell_points,
        "grid_index": [r.grid_index for r in sim.rows],
        "benchmark_returns": benchmark_returns,
        "benchmark_name": benchmark_name,
        "symbol_name": name,
        "summary": {
            "total_invested": float(summary.total_invested),
            "final_value": float(summary.final_value),
            "total_pnl": float(summary.total_pnl),
            "total_return_rate": float(summary.total_return_rate),
            "annualized_return": float(summary.annualized_return),
            "max_drawdown": float(summary.max_drawdown),
            "buy_count": summary.buy_count,
            "sell_count": summary.sell_count,
            "grid_profit": float(summary.grid_profit),
            "cycle_count": summary.cycle_count,
            "center_price": float(summary.center_price),
            "step_pct": float(summary.step_pct),
            "amount_per_level": float(summary.amount_per_level),
            "n_levels_above": summary.n_levels_above,
            "n_levels_below": summary.n_levels_below,
            "bound_mode": summary.bound_mode,
        },
    }


def _build_summary_orm(
    task_id: str, p: GridParams, sim: _GridSimResult, dates: list[date]
) -> ResultGridSummary:
    total_invested = sim.total_invested
    final_value = sim.final_value
    total_pnl = final_value - total_invested
    trr = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0
    annualized = annualized_return(sim.cashflows, trr, dates)
    mdd = max_drawdown(sim.market_values)

    return ResultGridSummary(
        task_id=task_id,
        symbol=p.symbol,
        center_price=p.center_price.quantize(_Q4),
        step_pct=p.step_pct.quantize(_Q4),
        amount_per_level=p.amount_per_level.quantize(_Q2),
        n_levels_above=p.n_levels_above,
        n_levels_below=p.n_levels_below,
        bound_mode=p.bound_mode,
        start_date=p.start_date,
        end_date=p.end_date,
        total_invested=Decimal(str(round(total_invested, 2))).quantize(_Q2),
        final_value=Decimal(str(round(final_value, 2))).quantize(_Q2),
        total_pnl=Decimal(str(round(total_pnl, 2))).quantize(_Q2),
        total_return_rate=Decimal(str(round(trr, 4))).quantize(_Q4),
        annualized_return=Decimal(str(round(annualized, 4))).quantize(_Q4),
        max_drawdown=Decimal(str(round(mdd, 4))).quantize(_Q4),
        buy_count=len(sim.buy_points),
        sell_count=len(sim.sell_points),
        grid_profit=Decimal(str(round(sim.grid_profit, 2))).quantize(_Q2),
        cycle_count=sim.cycle_count,
    )


def _write_results(
    db: Session, task_id: str, calc_rows: list[CalcGridBacktest], summary: ResultGridSummary
) -> None:
    db.execute(delete(CalcGridBacktest).where(CalcGridBacktest.task_id == task_id))
    db.execute(delete(ResultGridSummary).where(ResultGridSummary.task_id == task_id))
    db.add_all(calc_rows)
    db.add(summary)
    db.commit()


# --------------------------- DB 读取（GET /{task_id}/chart）---------------------------


def load_chart_rows(db: Session, task_id: str) -> list[CalcGridBacktest]:
    return (
        db.execute(
            select(CalcGridBacktest)
            .where(CalcGridBacktest.task_id == task_id)
            .order_by(CalcGridBacktest.trade_date)
        )
        .scalars()
        .all()
    )
