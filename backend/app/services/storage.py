"""行情数据持久化（增量 UPSERT），供数据拉取与回测自动补数据共用。"""

from datetime import date
from decimal import Decimal

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from ..models.raw import RawPriceDaily
from ..models.valuation import RawIndexValuationDaily
from .fetcher import PriceBar
from .fetcher.valuation_fetcher import ValuationBar


def upsert_bars(db: Session, bars: list[PriceBar], model=RawPriceDaily) -> int:
    """将行情写入目标表（默认 ``raw_price_daily``，Tushare 源传 ``RawPriceDailyTushare``）。

    主键 ``(symbol, trade_date)`` 冲突时更新，保证重复拉取幂等。返回写入条数。
    """
    if not bars:
        return 0
    rows = [
        {
            "symbol": b.symbol,
            "trade_date": b.trade_date,
            "open": b.open,
            "close": b.close,
            "high": b.high,
            "low": b.low,
            "volume": b.volume,
        }
        for b in bars
    ]
    stmt = mysql_insert(model).values(rows)
    stmt = stmt.on_duplicate_key_update(
        open=stmt.inserted.open,
        close=stmt.inserted.close,
        high=stmt.inserted.high,
        low=stmt.inserted.low,
        volume=stmt.inserted.volume,
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_valuation(db: Session, bars: list[ValuationBar]) -> int:
    """指数估值写入 ``raw_index_valuation_daily``（UPSERT 幂等）。

    主键 ``(index_code, trade_date)`` 冲突时更新 pe/pb/股息率/源。返回写入条数。
    """
    if not bars:
        return 0
    rows = [
        {
            "index_code": b.index_code,
            "trade_date": b.trade_date,
            "pe_ttm": b.pe_ttm,
            "pb": b.pb,
            "dividend_yield": b.dividend_yield,
            "source": b.source,
        }
        for b in bars
    ]
    stmt = mysql_insert(RawIndexValuationDaily).values(rows)
    stmt = stmt.on_duplicate_key_update(
        pe_ttm=stmt.inserted.pe_ttm,
        pb=stmt.inserted.pb,
        dividend_yield=stmt.inserted.dividend_yield,
        source=stmt.inserted.source,
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_dividend_snapshot(
    db: Session, index_code: str, trade_date: date, dividend_yield: Decimal | None
) -> None:
    """csindex 股息率当日快照（覆盖式 UPSERT）：**仅更新 dividend_yield 列**。

    冲突时不动 pe/pb（避免快照行把已有 PE 清空）。行不存在则插入（pe/pb 留空）。
    """
    stmt = mysql_insert(RawIndexValuationDaily).values(
        index_code=index_code,
        trade_date=trade_date,
        pe_ttm=None,
        pb=None,
        dividend_yield=dividend_yield,
        source="csindex",
    )
    stmt = stmt.on_duplicate_key_update(dividend_yield=stmt.inserted.dividend_yield)
    db.execute(stmt)
    db.commit()
