"""定投（DCA）回测计算引擎。

支持两种模式：
- ``normal``：普通定投，每期固定金额。
- ``smart``：智能定投（均线策略），按 T-1 日收盘价相对 MA(ma_period) 的偏离度
  动态调整扣款率——高位少投（最低 50%）、低位多投（最高 200%）。

所有金额/份额计算使用 Decimal；年化与最大回撤转 float 近似。
task_id 由全部参数（含 mode/ma_period）确定性生成，重复执行幂等。
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ...models.calc import CalcDcaBacktest
from ...models.result import ResultDcaSummary
from .common import annualized_return, compute_ma, load_prices, max_drawdown
from ..benchmark import compute_benchmark_returns
from ..symbol_catalog import lookup_name

_Q8 = Decimal("0.00000001")  # 份额 8 位
_Q4 = Decimal("0.0001")  # 百分比/扣款率 4 位
_Q2 = Decimal("0.01")  # 金额 2 位


class ComputeError(Exception):
    """回测计算业务异常。"""


@dataclass(frozen=True)
class DcaParams:
    symbol: str
    frequency: str  # 'weekly' | 'monthly'
    amount: Decimal
    start_date: date
    end_date: date
    invest_day: int  # weekly: 0-6; monthly: 1-28
    mode: str = "normal"  # 'normal' | 'smart'
    ma_period: int = 250
    source: str = "akshare"  # 数据源：非 akshare 时 task_id 追加后缀，使两源结果互不覆盖


def make_task_id(p: DcaParams) -> str:
    """由全部参数确定性生成 task_id（含 mode/ma_period），保证幂等。

    默认源（akshare）task_id 与历史完全一致，旧缓存可平滑命中；
    非 akshare 源末尾追加 ``_{source}``（如 ``_tushare``），与 AkShare 结果隔离。
    """
    base = (
        f"dca_{p.symbol}_{p.start_date:%Y%m%d}_{p.end_date:%Y%m%d}"
        f"_{p.frequency}_{p.amount}_{p.invest_day}_{p.mode}_{p.ma_period}"
    )
    return f"{base}_{p.source}" if p.source != "akshare" else base


def lookback_days(mode: str, ma_period: int) -> int:
    """智能模式需回溯足够历史以计算 MA；返回额外向前加载的日历天数。"""
    return ma_period * 2 if mode == "smart" else 0


def _compute(db: Session, p: DcaParams):
    """校验 + 加载行情 + 逐日计算 + 汇总（不落库）。返回 (task_id, calc_rows, summary, all_days)。"""
    task_id = make_task_id(p)
    load_start = p.start_date - timedelta(days=lookback_days(p.mode, p.ma_period))

    all_days = load_prices(db, p.symbol, load_start, p.end_date, p.source)
    if not any(d >= p.start_date for d, _ in all_days):
        raise ComputeError(
            f"标的 {p.symbol} 在 {p.start_date}~{p.end_date} 无行情数据，请先拉取数据"
        )

    ma_series = compute_ma(all_days, p.ma_period) if p.mode == "smart" else {}
    invest_dates = _gen_invest_dates(p, [(d, c) for d, c in all_days if d >= p.start_date])

    calc_rows, market_values, cashflows, invest_count = _daily_calc(
        task_id, p, all_days, ma_series, invest_dates
    )
    dates = [r.trade_date for r in calc_rows]
    summary = _build_summary(task_id, p, dates, market_values, cashflows, invest_count)
    return task_id, calc_rows, summary, all_days


def run_backtest(db: Session, p: DcaParams) -> str:
    """执行回测并落库（calc + result 两表，幂等先删后写）。返回 task_id。"""
    task_id, calc_rows, summary, _ = _compute(db, p)
    _write_results(db, task_id, calc_rows, summary)
    return task_id


def run_realtime(db: Session, p: DcaParams) -> dict:
    """实时回测（不落库）：返回 chart 数据 + summary，供「开始回测」预览。"""
    task_id, calc_rows, summary, all_days = _compute(db, p)
    trade_dates = [r.trade_date for r in calc_rows]
    benchmark_returns, benchmark_name = compute_benchmark_returns(
        db, trade_dates, p.start_date, p.end_date, source=p.source
    )
    name = lookup_name(p.symbol)
    return {
        "dates": trade_dates,
        "market_value": [float(r.market_value) for r in calc_rows],
        "total_cost": [float(r.cum_cost) for r in calc_rows],
        "pnl": [float(r.pnl) for r in calc_rows],
        "return_rate": [float(r.return_rate) for r in calc_rows],
        "invest_days": [bool(r.is_invest_day) for r in calc_rows],
        "deduction_rates": [
            float(r.deduction_rate) if (r.is_invest_day and r.deduction_rate is not None) else None
            for r in calc_rows
        ],
        "actual_amounts": [
            float(r.actual_amount) if (r.is_invest_day and r.actual_amount is not None) else None
            for r in calc_rows
        ],
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
            "invest_count": summary.invest_count,
            "symbol_name": name,
        },
    }


# --------------------------- 智能定投策略 ---------------------------


def _deduction_rate(deviation_pct: float) -> Decimal:
    """按偏离度(%)查扣款率表。高位少投(≥0)，低位多投(<0)。"""
    x = deviation_pct
    if x >= 0:  # 高位少投，下限 50%
        if x < 2:
            r = 1.0
        elif x < 4:
            r = 0.9
        elif x < 6:
            r = 0.8
        elif x < 8:
            r = 0.7
        elif x < 10:
            r = 0.6
        else:
            r = 0.5
    else:  # 低位多投，上限 200%
        if x >= -2:
            r = 1.0
        elif x >= -4:
            r = 1.1
        elif x >= -6:
            r = 1.2
        elif x >= -8:
            r = 1.3
        elif x >= -10:
            r = 1.4
        elif x >= -12:
            r = 1.5
        elif x >= -14:
            r = 1.6
        elif x >= -16:
            r = 1.7
        elif x >= -18:
            r = 1.8
        elif x >= -20:
            r = 1.9
        else:
            r = 2.0
    return Decimal(str(r)).quantize(_Q4)


def _smart_rate(
    d: date,
    prev_date: dict[date, date | None],
    close_by_date: dict[date, Decimal],
    ma_series: dict[date, Decimal],
) -> Decimal:
    """取 T-1 日收盘价与 MA 算偏离度 → 扣款率；数据不足回退 100%。"""
    t1 = prev_date.get(d)
    if not t1:
        return Decimal("1.0000")
    t1_close = close_by_date.get(t1)
    t1_ma = ma_series.get(t1)
    if not t1_close or not t1_ma or t1_ma <= 0:
        return Decimal("1.0000")
    dev = float((t1_close - t1_ma) / t1_ma * Decimal(100))
    return _deduction_rate(dev)


# --------------------------- 内部实现 ---------------------------


def _gen_invest_dates(p: DcaParams, trading_days: list[tuple[date, Decimal]]) -> set[date]:
    """生成定投日历；非交易日的候选日顺延至下一个交易日。"""
    trading_set = {d for d, _ in trading_days}
    sorted_days = sorted(trading_set)

    candidates: list[date] = []
    if p.frequency == "weekly":
        cur = p.start_date + timedelta(days=(p.invest_day - p.start_date.weekday()) % 7)
        while cur <= p.end_date:
            candidates.append(cur)
            cur = cur + timedelta(weeks=1)
    elif p.frequency == "monthly":
        y, m = p.start_date.year, p.start_date.month
        while (y, m) <= (p.end_date.year, p.end_date.month):
            try:
                candidates.append(date(y, m, p.invest_day))
            except ValueError:
                pass
            m += 1
            if m > 12:
                m, y = 1, y + 1
    else:
        raise ComputeError(f"不支持的定投频率: {p.frequency}")

    result: set[date] = set()
    for c in candidates:
        if c in trading_set:
            result.add(c)
            continue
        for td in sorted_days:
            if td >= c:
                if td <= p.end_date:
                    result.add(td)
                break
    return result


def _daily_calc(task_id, p, all_days, ma_series, invest_dates):
    close_by_date = {d: c for d, c in all_days}
    sorted_dates = [d for d, _ in all_days]
    prev_date: dict[date, date | None] = {}
    for i in range(len(sorted_dates)):
        prev_date[sorted_dates[i]] = sorted_dates[i - 1] if i > 0 else None

    cum_shares = Decimal(0)
    cum_cost = Decimal(0)
    calc_rows: list[CalcDcaBacktest] = []
    market_values: list[float] = []
    cashflows: list[tuple[date, float]] = []
    invest_count = 0

    for d, close in all_days:
        if d < p.start_date:
            continue
        is_invest = d in invest_dates
        buy_shares = Decimal(0)
        deduction_rate: Decimal | None = None
        actual_amount = Decimal(0)
        if is_invest:
            deduction_rate = (
                _smart_rate(d, prev_date, close_by_date, ma_series)
                if p.mode == "smart"
                else Decimal("1.0000")
            )
            actual_amount = (p.amount * deduction_rate).quantize(_Q2)
            buy_shares = (actual_amount / close).quantize(_Q8)
            cum_shares += buy_shares
            cum_cost += actual_amount
            invest_count += 1
            cashflows.append((d, -float(actual_amount)))

        market_value = (cum_shares * close).quantize(_Q2)
        pnl = (market_value - cum_cost).quantize(_Q2)
        return_rate = ((pnl / cum_cost) * Decimal(100)).quantize(_Q4) if cum_cost > 0 else Decimal(0)

        calc_rows.append(
            CalcDcaBacktest(
                task_id=task_id,
                trade_date=d,
                is_invest_day=1 if is_invest else 0,
                buy_shares=buy_shares,
                cum_shares=cum_shares.quantize(_Q8),
                cum_cost=cum_cost.quantize(_Q2),
                market_value=market_value,
                pnl=pnl,
                return_rate=return_rate,
                deduction_rate=deduction_rate,
                actual_amount=actual_amount if is_invest else None,
            )
        )
        market_values.append(float(market_value))

    if calc_rows:
        last_date = calc_rows[-1].trade_date
        cashflows.append((last_date, market_values[-1]))

    return calc_rows, market_values, cashflows, invest_count


def _build_summary(task_id, p, dates, market_values, cashflows, invest_count):
    total_invested = -sum(cf[1] for cf in cashflows if cf[1] < 0)
    final_value = market_values[-1] if market_values else 0.0
    total_pnl = final_value - total_invested
    total_return_rate = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    annualized = annualized_return(cashflows, total_return_rate, dates)
    mdd_val = max_drawdown(market_values)

    return ResultDcaSummary(
        task_id=task_id,
        symbol=p.symbol,
        frequency=p.frequency,
        amount=p.amount,
        invest_day=p.invest_day,
        start_date=p.start_date,
        end_date=p.end_date,
        total_invested=Decimal(str(total_invested)).quantize(_Q2),
        final_value=Decimal(str(final_value)).quantize(_Q2),
        total_pnl=Decimal(str(total_pnl)).quantize(_Q2),
        total_return_rate=Decimal(str(round(total_return_rate, 4))),
        annualized_return=Decimal(str(round(annualized, 4))),
        max_drawdown=Decimal(str(round(mdd_val, 4))),
        invest_count=invest_count,
    )


def _write_results(
    db: Session, task_id: str, calc_rows: list[CalcDcaBacktest], summary: ResultDcaSummary
):
    db.execute(delete(CalcDcaBacktest).where(CalcDcaBacktest.task_id == task_id))
    db.execute(delete(ResultDcaSummary).where(ResultDcaSummary.task_id == task_id))
    db.add_all(calc_rows)
    db.add(summary)
    db.commit()
