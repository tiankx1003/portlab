"""定投（DCA）回测计算引擎。

所有金额/份额计算使用 Decimal 保证精度；年化收益率（XIRR）与最大回撤
属于近似统计指标，转 float 计算。

幂等：task_id 由参数确定性生成，重复执行同一组参数会先删除旧结果再重算，
不会产生重复数据。
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ...models.calc import CalcDcaBacktest
from ...models.raw import RawPriceDaily
from ...models.result import ResultDcaSummary

_Q8 = Decimal("0.00000001")  # 份额 8 位
_Q2 = Decimal("0.01")  # 金额 2 位
_Q4 = Decimal("0.0001")  # 百分比 4 位


class ComputeError(Exception):
    """回测计算业务异常。"""


@dataclass(frozen=True)
class DcaParams:
    symbol: str
    frequency: str  # 'weekly' | 'monthly'
    amount: Decimal
    start_date: date
    end_date: date
    invest_day: int  # weekly: 0-6(周一~周日); monthly: 1-28


def make_task_id(p: DcaParams) -> str:
    """由参数确定性生成 task_id（同名参数 → 同 id，保证幂等）。"""
    return (
        f"dca_{p.symbol}_{p.start_date:%Y%m%d}_{p.end_date:%Y%m%d}"
        f"_{p.frequency}_{p.amount}_{p.invest_day}"
    )


def run_backtest(db: Session, p: DcaParams) -> str:
    """执行回测，逐日结果写入 calc_dca_backtest，汇总写入 result_dca_summary。返回 task_id。"""
    task_id = make_task_id(p)

    trading_days = _load_prices(db, p)
    if not trading_days:
        raise ComputeError(
            f"标的 {p.symbol} 在 {p.start_date}~{p.end_date} 无行情数据，请先拉取数据"
        )

    invest_dates = _gen_invest_dates(p, trading_days)

    calc_rows, market_values, cashflows, invest_count = _daily_calc(task_id, p, trading_days, invest_dates)

    summary = _build_summary(task_id, p, trading_days, market_values, cashflows, invest_count)

    _write_results(db, task_id, calc_rows, summary)
    return task_id


# --------------------------- 内部实现 ---------------------------


def _load_prices(db: Session, p: DcaParams) -> list[tuple[date, Decimal]]:
    rows = db.execute(
        select(RawPriceDaily.trade_date, RawPriceDaily.close)
        .where(
            RawPriceDaily.symbol == p.symbol,
            RawPriceDaily.trade_date >= p.start_date,
            RawPriceDaily.trade_date <= p.end_date,
        )
        .order_by(RawPriceDaily.trade_date)
    ).all()
    return [(r.trade_date, Decimal(str(r.close))) for r in rows]


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
                pass  # invest_day 不合法（理论上 1-28 不会触发）
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
        # 顺延到下一个 >= c 的交易日
        for td in sorted_days:
            if td >= c:
                if td <= p.end_date:
                    result.add(td)
                break
    return result


def _daily_calc(task_id, p, trading_days, invest_dates):
    cum_shares = Decimal(0)
    cum_cost = Decimal(0)
    calc_rows: list[CalcDcaBacktest] = []
    market_values: list[float] = []
    cashflows: list[tuple[date, float]] = []
    invest_count = 0

    for d, close in trading_days:
        is_invest = d in invest_dates
        buy_shares = Decimal(0)
        if is_invest:
            buy_shares = (p.amount / close).quantize(_Q8)
            cum_shares += buy_shares
            cum_cost += p.amount
            invest_count += 1
            cashflows.append((d, -float(p.amount)))

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
            )
        )
        market_values.append(float(market_value))

    # 期末一次性"清仓"作为终值现金流入，用于 XIRR
    if trading_days:
        last_date = trading_days[-1][0]
        cashflows.append((last_date, market_values[-1]))

    return calc_rows, market_values, cashflows, invest_count


def _build_summary(task_id, p, trading_days, market_values, cashflows, invest_count):
    # 累计投入 = 所有现金流出（负值）取绝对值之和
    total_invested = -sum(cf[1] for cf in cashflows if cf[1] < 0)
    final_value = market_values[-1] if market_values else 0.0
    total_pnl = final_value - total_invested
    total_return_rate = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    dates = [d for d, _ in trading_days]
    annualized = _annualized(cashflows, total_return_rate, dates)
    max_drawdown = _max_drawdown(market_values)

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
        max_drawdown=Decimal(str(round(max_drawdown, 4))),
        invest_count=invest_count,
    )


def _write_results(db: Session, task_id: str, calc_rows: list[CalcDcaBacktest], summary: ResultDcaSummary):
    db.execute(delete(CalcDcaBacktest).where(CalcDcaBacktest.task_id == task_id))
    db.execute(delete(ResultDcaSummary).where(ResultDcaSummary.task_id == task_id))
    db.add_all(calc_rows)
    db.add(summary)
    db.commit()


def _annualized(cashflows: list[tuple[date, float]], total_return_rate: float, dates: list[date]) -> float:
    """年化收益率：优先 XIRR（DCA 多笔现金流的正确口径），失败回退持有期近似。"""
    x = _xirr(cashflows)
    if x is not None:
        return x * 100
    if len(dates) >= 2:
        yrs = (dates[-1] - dates[0]).days / 365.0
        base = 1 + total_return_rate / 100
        if yrs > 0 and base > 0:
            return (base ** (1 / yrs) - 1) * 100
    return total_return_rate


def _xirr(cashflows: list[tuple[date, float]], ) -> float | None:
    """XIRR（年化内部收益率），二分法求解 NPV=0。"""
    if not cashflows:
        return None
    cashflows = sorted(cashflows, key=lambda x: x[0])
    t0 = cashflows[0][0]

    def npv(rate: float) -> float:
        if rate <= -1:
            return float("inf")
        total = 0.0
        for d, amt in cashflows:
            yrs = (d - t0).days / 365.0
            total += amt / ((1 + rate) ** yrs)
        return total

    lo, hi = -0.9999, 10.0
    flo, fhi = npv(lo), npv(hi)
    if flo == fhi or flo * fhi > 0:
        return None  # 区间内无变号，放弃
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = npv(mid)
        if abs(fm) < 1e-7 or (hi - lo) < 1e-10:
            return mid
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def _max_drawdown(series: list[float]) -> float:
    """基于市值曲线的最大回撤（%）。"""
    if not series:
        return 0.0
    peak = series[0]
    mdd = 0.0
    for v in series:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            if dd > mdd:
                mdd = dd
    return mdd * 100
