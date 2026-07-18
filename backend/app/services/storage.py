"""行情数据持久化（增量 UPSERT），供数据拉取与回测自动补数据共用。"""

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from ..models.raw import RawPriceDaily
from .fetcher import PriceBar


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
