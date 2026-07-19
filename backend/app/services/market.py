"""市场概览服务：从 raw_price_daily 读取预置指数的最新价 / 涨跌幅 / sparkline。

一期硬编码预置指数列表（3 个）+ 第 4 格由前端传入 ``extra`` 自定义代码；不主动拉取
（拉取由前端复用 /api/data/fetch 触发）。
"""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from .fetcher.registry import SOURCE_TABLE, resolve_source
from .symbol_catalog import lookup_name

# 预置指数：代码 -> 名称（第 4 格由用户手动输入，见 get_market_overview 的 extra）
OVERVIEW_SYMBOLS: list[tuple[str, str]] = [
    ("510300", "沪深300ETF"),
    ("510880", "红利ETF"),
    ("512890", "红利低波ETF"),
]

# sparkline 取最近 N 个交易日收盘
_SPARKLINE_DAYS = 30


def get_market_overview(db: Session, extra: str | None = None) -> dict:
    """读取预置指数 + 可选自定义代码的概览。仅读 raw_price_daily，不拉取。

    ``extra`` 为前端第 4 格手动输入的代码（自动剥离 SH/SZ 前缀、去重）。
    随数据源开关读对应源表（akshare→raw_price_daily；tushare→raw_price_daily_tushare）。
    返回: {as_of, items: [...], missing: [...]}
    """
    src = resolve_source(db)
    model = SOURCE_TABLE[src]

    # 预置指数：名称用全名（symbol_catalog 解析），解析不到回退短名
    symbols: list[tuple[str, str]] = [(c, lookup_name(c) or n) for c, n in OVERVIEW_SYMBOLS]
    if extra:
        from ..utils.symbol import strip_market_prefix

        code = strip_market_prefix(extra).strip()
        if code and code not in {s for s, _ in symbols}:
            symbols.append((code, lookup_name(code) or code))

    items: list[dict] = []
    missing: list[str] = []
    as_of: date | None = None

    for symbol, name in symbols:
        # 最近 N 个交易日（倒序取，再翻转为升序供 sparkline）
        rows = (
            db.execute(
                select(model.trade_date, model.close)
                .where(model.symbol == symbol)
                .order_by(model.trade_date.desc())
                .limit(_SPARKLINE_DAYS)
            )
            .all()
        )
        if not rows:
            missing.append(symbol)
            continue

        latest_date = rows[0].trade_date
        latest_close = float(rows[0].close)
        prev_close = float(rows[1].close) if len(rows) > 1 else None
        change_pct = (
            round((latest_close - prev_close) / prev_close * 100, 4) if prev_close else None
        )
        sparkline = [float(r.close) for r in reversed(rows)]

        items.append(
            {
                "symbol": symbol,
                "name": name,
                "latest_date": latest_date,
                "latest_close": latest_close,
                "prev_close": prev_close,
                "change_pct": change_pct,
                "sparkline": sparkline,
            }
        )
        if as_of is None or latest_date > as_of:
            as_of = latest_date

    return {"as_of": as_of, "items": items, "missing": missing}

