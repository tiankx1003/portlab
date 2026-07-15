"""收益率基准（沪深300）计算，DCA / MA120 回测共用。

基准用 510300 ETF 代表沪深300，收益率与指数一致。
"""

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.raw import RawPriceDaily

BENCHMARK_SYMBOL = "510300"
BENCHMARK_NAME = "沪深300"


def compute_benchmark_returns(
    db: Session,
    trade_dates: list[date],
    start_date: date,
    end_date: date,
) -> tuple[list[float | None], str]:
    """沪深300 在 [start_date, end_date] 的累计收益率（相对区间首日），按 trade_dates 对齐。

    无基准数据时返回 ([None, ...], "")；有数据但无有效起点时返回 ([None, ...], 名称)。
    """
    if not trade_dates:
        return [], ""

    bench = {
        r.trade_date: Decimal(str(r.close))
        for r in db.execute(
            select(RawPriceDaily.trade_date, RawPriceDaily.close).where(
                RawPriceDaily.symbol == BENCHMARK_SYMBOL,
                RawPriceDaily.trade_date >= start_date,
                RawPriceDaily.trade_date <= end_date,
            )
        ).all()
    }
    if not bench:
        return [None] * len(trade_dates), ""

    # 基准起点：区间首个交易日（或之后首个有数据的交易日）
    first_date = trade_dates[0]
    base_close = bench.get(first_date)
    if base_close is None:
        for d in sorted(bench):
            if d >= first_date:
                base_close = bench[d]
                break
    if not base_close or base_close <= 0:
        return [None] * len(trade_dates), BENCHMARK_NAME

    out: list[float | None] = []
    for d in trade_dates:
        c = bench.get(d)
        out.append(float((c / base_close - 1) * 100) if c else None)
    return out, BENCHMARK_NAME
