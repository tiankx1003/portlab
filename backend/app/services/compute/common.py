"""计算引擎公共工具（DCA / MA120 共用）。

包含：行情加载、滚动均线、最大回撤、XIRR 年化。
金额/份额用 Decimal 精确计算；年化与回撤转 float 近似。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models.raw import RawPriceDaily

_Q4 = Decimal("0.0001")  # 百分比 / 均线 4 位


def load_prices(
    db: Session, symbol: str, start: date, end: date
) -> list[tuple[date, Decimal]]:
    """从 raw_price_daily 读取 [start, end] 收盘价（按日期升序）。"""
    rows = db.execute(
        select(RawPriceDaily.trade_date, RawPriceDaily.close)
        .where(
            RawPriceDaily.symbol == symbol,
            RawPriceDaily.trade_date >= start,
            RawPriceDaily.trade_date <= end,
        )
        .order_by(RawPriceDaily.trade_date)
    ).all()
    return [(r.trade_date, Decimal(str(r.close))) for r in rows]


def compute_ma(days: list[tuple[date, Decimal]], period: int) -> dict[date, Decimal]:
    """滚动简单均线（前缀和），仅对历史 ≥ period 的日期给出值。"""
    dates = [d for d, _ in days]
    closes = [c for _, c in days]
    n = len(closes)
    prefix: list[Decimal] = [Decimal(0)]
    for c in closes:
        prefix.append(prefix[-1] + c)
    ma: dict[date, Decimal] = {}
    big_period = Decimal(period)
    for i in range(n):
        if i >= period - 1:
            window_sum = prefix[i + 1] - prefix[i + 1 - period]
            ma[dates[i]] = (window_sum / big_period).quantize(_Q4)
    return ma


def max_drawdown(series: list[float]) -> float:
    """序列最大回撤（%）。"""
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


def xirr(cashflows: list[tuple[date, float]]) -> float | None:
    """二分法求解 XIRR；无解返回 None。cashflows: [(日期, 现金流)]，投入为负。"""
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
        return None
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


def annualized_return(
    cashflows: list[tuple[date, float]],
    total_return_rate: float,
    dates: list[date],
) -> float:
    """年化收益率(%)：优先 XIRR；现金流无解时回退为 (1+r)^(1/yrs)-1。"""
    x = xirr(cashflows)
    if x is not None:
        return x * 100
    if len(dates) >= 2:
        yrs = (dates[-1] - dates[0]).days / 365.0
        base = 1 + total_return_rate / 100
        if yrs > 0 and base > 0:
            return (base ** (1 / yrs) - 1) * 100
    return total_return_rate
