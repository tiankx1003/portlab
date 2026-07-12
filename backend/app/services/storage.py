"""行情数据持久化（增量 UPSERT），供数据拉取与回测自动补数据共用。"""

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from ..models.raw import RawPriceDaily
from .fetcher import PriceBar


def upsert_bars(db: Session, bars: list[PriceBar]) -> int:
    """将行情写入 raw_price_daily，主键冲突时更新。返回写入条数。"""
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
    stmt = mysql_insert(RawPriceDaily).values(rows)
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
