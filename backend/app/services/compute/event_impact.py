"""事件冲击指标计算（事件冲击产业链看板 018）。

三个核心函数：
- ``event_window_returns``：事件窗口归一化收益序列（事件日=0 基准），供视图②多曲线。
- ``window_cumulative_change``：事件日→事件后 N 日累计涨跌幅(%)，供视图②排行榜。
- ``correlation_matrix``：标的池日收益率两两皮尔逊相关矩阵，供视图③热力图。

行情读自生效数据源表（``resolve_source`` → ``raw_price_daily`` / ``_tushare``），
缺失区间用 ``ensure_price_data`` 补拉（复用 002 范式）。一期数据量小（几十标的×几十天），
纯 Python 实现相关系数，不引入 numpy。
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..fetcher.registry import SOURCE_TABLE, resolve_source
from ..price_data import ensure_price_data

logger = logging.getLogger(__name__)

# 拉取窗口前后的日历日缓冲（覆盖春节等长假，确保能取到事件日前一个交易日）
_FRONT_BUFFER = timedelta(days=10)


def _load_closes(
    db: Session, symbol: str, start: date, end: date
) -> list[tuple[date, float]]:
    """确保区间行情完整后，返回 (trade_date, close) 升序列表。补拉失败则返回已有部分。"""
    src = resolve_source(db)
    model = SOURCE_TABLE[src]
    err = ensure_price_data(db, symbol, start, end)
    if err:
        logger.info("事件窗口行情补拉告警：%s", err)
    rows = db.execute(
        select(model.trade_date, model.close)
        .where(
            model.symbol == symbol,
            model.trade_date >= start,
            model.trade_date <= end,
        )
        .order_by(model.trade_date)
    ).all()
    return [(_to_date(r[0]), _to_float(r[1])) for r in rows]


def _to_date(v) -> date:
    return v if isinstance(v, date) else v.date()


def _to_float(v) -> float:
    return float(v) if isinstance(v, (Decimal, int, float)) else float(v or 0.0)


def _baseline_close(series: list[tuple[date, float]], event_date: date) -> float | None:
    """事件日基准收盘：取 ≤ event_date 的最近一个交易日收盘。"""
    base = None
    for d, c in series:
        if d <= event_date:
            base = c
        else:
            break
    return base


def event_window_returns(
    db: Session, symbols: list[str], event_date: date, before: int, after: int
) -> dict[str, list[tuple[date, float]]]:
    """每个标的在 [event_date-before, event_date+after] 的归一化收益序列。

    归一化：事件日（或其前最近交易日）收盘 = 0 基准，其余日为累计收益率(%)。
    """
    before = max(0, int(before))
    after = max(0, int(after))
    win_start = event_date - timedelta(days=before)
    win_end = event_date + timedelta(days=after)
    fetch_start = win_start - _FRONT_BUFFER

    out: dict[str, list[tuple[date, float]]] = {}
    for sym in symbols:
        series = _load_closes(db, sym, fetch_start, win_end)
        if not series:
            continue
        base = _baseline_close(series, event_date)
        if not base:
            continue
        out[sym] = [
            (d, (c / base - 1) * 100)
            for d, c in series
            if win_start <= d <= win_end
        ]
    return out


def window_cumulative_change(
    db: Session, symbols: list[str], event_date: date, after: int
) -> dict[str, float]:
    """每标的 event_date → event_date+after 的累计涨跌幅(%)。

    基准 = ≤ event_date 最近交易日收盘；终点 = ≤ event_date+after 最近交易日收盘。
    """
    after = max(0, int(after))
    win_end = event_date + timedelta(days=after)
    fetch_start = event_date - _FRONT_BUFFER

    out: dict[str, float] = {}
    for sym in symbols:
        series = _load_closes(db, sym, fetch_start, win_end)
        if not series:
            continue
        base = _baseline_close(series, event_date)
        if not base:
            continue
        end_close = None
        for d, c in series:
            if d <= win_end:
                end_close = c
            else:
                break
        if end_close is None:
            continue
        out[sym] = (end_close / base - 1) * 100
    return out


def correlation_matrix(
    db: Session, symbols: list[str], event_date: date, before: int, after: int
) -> list[list[float]]:
    """标的池内日收益率两两皮尔逊相关系数矩阵（对角线=1，对称）。"""
    before = max(0, int(before))
    after = max(0, int(after))
    win_start = event_date - timedelta(days=before)
    win_end = event_date + timedelta(days=after)
    fetch_start = win_start - _FRONT_BUFFER

    # 每标的的日收益率序列（按日期），仅取窗口内
    returns_by_sym: dict[str, dict[date, float]] = {}
    all_dates: set[date] = set()
    for sym in symbols:
        series = _load_closes(db, sym, fetch_start, win_end)
        dr: dict[date, float] = {}
        prev: tuple[date, float] | None = None
        for d, c in series:
            if prev is not None and prev[1] != 0:
                if win_start <= d <= win_end:
                    dr[d] = c / prev[1] - 1
            prev = (d, c)
        if dr:
            returns_by_sym[sym] = dr
            all_dates |= set(dr.keys())

    n = len(symbols)
    if n == 0:
        return []
    dates_sorted = sorted(all_dates)
    vecs = [
        [returns_by_sym.get(sym, {}).get(d) for d in dates_sorted] for sym in symbols
    ]

    matrix: list[list[float]] = [[1.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            xs: list[float] = []
            ys: list[float] = []
            for a, b in zip(vecs[i], vecs[j], strict=False):
                if a is not None and b is not None:
                    xs.append(a)
                    ys.append(b)
            c = _pearson(xs, ys)
            matrix[i][j] = c
            matrix[j][i] = c
    return matrix


def _pearson(xs: list[float], ys: list[float]) -> float:
    """皮尔逊相关系数；样本不足或方差为 0 返回 0（无可测线性相关）。"""
    n = len(xs)
    if n < 2:
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    dx = sum((x - mx) ** 2 for x in xs) ** 0.5
    dy = sum((y - my) ** 2 for y in ys) ** 0.5
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)
