"""行情数据持久化（增量 UPSERT），供数据拉取与回测自动补数据共用。"""

from datetime import date
from decimal import Decimal

from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from ..models.etf_share import RawEtfShareDaily
from ..models.raw import RawPriceDaily
from ..models.signal_board import (
    RawBondYieldDaily,
    RawIndexDaily,
    RawMacroIndicator,
    RawMarginBalance,
)
from ..models.valuation import RawIndexValuationDaily
from .fetcher import PriceBar
from .fetcher.signal_fetcher import BondBar, IndexBar
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


def upsert_etf_shares(db: Session, rows: list[dict]) -> int:
    """ETF 每日份额写入 ``raw_etf_share_daily``（UPSERT 幂等）。

    主键 ``(symbol, trade_date)`` 冲突时更新 fd_share/source。返回写入条数。
    rows 元素：{"symbol", "trade_date", "fd_share", "source"}。
    """
    if not rows:
        return 0
    stmt = mysql_insert(RawEtfShareDaily).values(rows)
    stmt = stmt.on_duplicate_key_update(
        fd_share=stmt.inserted.fd_share,
        source=stmt.inserted.source,
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_bond_yield(db: Session, bars: list[BondBar]) -> int:
    """十年期国债收益率写入 ``raw_bond_yield_daily``（UPSERT 幂等）。

    主键 ``(trade_date)`` 冲突时更新 yield_10y/source。返回写入条数。
    """
    if not bars:
        return 0
    rows = [
        {"trade_date": b.trade_date, "yield_10y": b.yield_10y, "source": b.source}
        for b in bars
    ]
    stmt = mysql_insert(RawBondYieldDaily).values(rows)
    stmt = stmt.on_duplicate_key_update(
        yield_10y=stmt.inserted.yield_10y,
        source=stmt.inserted.source,
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_index_close(db: Session, bars: list[IndexBar]) -> int:
    """指数日线点位写入 ``raw_index_daily``（UPSERT 幂等）。

    主键 ``(index_code, trade_date)`` 冲突时更新 close/index_type/source。返回写入条数。
    """
    if not bars:
        return 0
    rows = [
        {
            "index_code": b.index_code,
            "trade_date": b.trade_date,
            "close": b.close,
            "index_type": b.index_type,
            "source": b.source,
        }
        for b in bars
    ]
    stmt = mysql_insert(RawIndexDaily).values(rows)
    stmt = stmt.on_duplicate_key_update(
        close=stmt.inserted.close,
        index_type=stmt.inserted.index_type,
        source=stmt.inserted.source,
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_macro(db: Session, bars: list) -> int:
    """宏观指标写入 ``raw_macro_indicator``（UPSERT 幂等）。

    主键 ``(indicator, ref_date)`` 冲突时更新 value/source。bars 为 MacroBar 列表。
    """
    if not bars:
        return 0
    from decimal import Decimal  # noqa: PLC0415

    rows = [
        {
            "indicator": b.indicator,
            "ref_date": b.ref_date,
            "value": Decimal(str(b.value)) if b.value is not None else None,
            "source": b.source,
        }
        for b in bars
    ]
    stmt = mysql_insert(RawMacroIndicator).values(rows)
    stmt = stmt.on_duplicate_key_update(
        value=stmt.inserted.value,
        source=stmt.inserted.source,
    )
    db.execute(stmt)
    db.commit()
    return len(rows)


def upsert_margin(db: Session, rows: list[dict]) -> int:
    """融资融券余额写入 ``raw_margin_balance``（UPSERT 幂等）。

    主键 ``(trade_date)`` 冲突时更新 rzye/rqye/source。返回写入条数。
    rows 元素：{"trade_date", "rzye", "rqye", "source"}。
    """
    if not rows:
        return 0
    from decimal import Decimal  # noqa: PLC0415

    norm = []
    for r in rows:
        norm.append(
            {
                "trade_date": r["trade_date"],
                "rzye": Decimal(str(r["rzye"])) if r.get("rzye") is not None else None,
                "rqye": Decimal(str(r["rqye"])) if r.get("rqye") is not None else None,
                "source": r.get("source", "tushare"),
            }
        )
    stmt = mysql_insert(RawMarginBalance).values(norm)
    stmt = stmt.on_duplicate_key_update(
        rzye=stmt.inserted.rzye,
        rqye=stmt.inserted.rqye,
        source=stmt.inserted.source,
    )
    db.execute(stmt)
    db.commit()
    return len(norm)
