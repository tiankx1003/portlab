"""PCF 入库服务：把爬虫/CSV 产出的行 dict 写入 raw_pcf_basket / raw_pcf_day_info。

设计要点
--------
- 输入行 dict 以「爬虫 CSV 列名」为键（如 ``fundCode``/``tradingDay``/``stockCode``），
  与各爬虫 ``normalize_*`` 的输出、以及 ``csv.DictReader`` 的输出完全一致 ——
  因此「实时抓取 ``--db``」与「离线 CSV 入库」两条入口复用同一份映射逻辑。
- 按 ``(source, fund_code, trading_day)`` 先删后批量插，重抓幂等。
- 空串 -> NULL；金额/比例 -> Decimal；整数 -> int；日期支持 YYYYMMDD 与 YYYY-MM-DD。
- 未知 source 抛错（成份券表）或静默跳过（头部表，如 fsfund 无头部）。
"""

from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import delete, insert
from sqlalchemy.orm import Session

from ..models.pcf import RawPcfBasket, RawPcfDayInfo

# ---- 字段映射：爬虫 CSV 列名 -> DB 列名（每家一套）------------------------
BASKET_FIELD_MAP: dict[str, dict[str, str]] = {
    "fsfund": {
        "fundCode": "fund_code", "tradingDay": "trading_day", "id": "record_id",
        "fundId": "fund_id", "scid": "scid", "stockCode": "stock_code",
        "stockShort": "stock_short", "number": "number", "tdbz": "tdbz",
        "tdje": "tdje", "sgtdje": "sgtdje", "shtdje": "shtdje",
        "yjbl": "yjbl", "sgyjbl": "sg_yjbl", "shzjbl": "sh_zjbl",
        "gpsc": "gpsc", "stockCodesrc": "stock_codesrc", "mmbz": "mmbz",
        "reserved": "reserved", "procFlag": "procflag",
    },
    "huatai_pb": {
        "fundCode": "fund_code", "fundCodes": "fund_codes", "fundName": "fund_name",
        "tradingDay": "trading_day", "fundId": "fund_id", "stockCode": "stock_code",
        "stockShort": "stock_short", "gpsc": "gpsc", "stockCodesrc": "stock_codesrc",
        "number": "number", "tdje": "tdje", "sgtdje": "sgtdje", "shtdje": "shtdje",
        "yjbl": "yjbl", "discountrate": "discount_rate", "premiumrate": "premium_rate",
        "tdbz": "tdbz", "buyorsell": "buyorsell",
    },
}

DAYINFO_FIELD_MAP: dict[str, dict[str, str]] = {
    "huatai_pb": {
        "fundCode": "fund_code", "fundName": "fund_name", "tradingDay": "trading_day",
        "nav": "nav", "cashcomponent": "cash_component",
        "estimatecashcomponent": "estimate_cash_component",
        "cashdividend": "cash_dividend", "creationredemptionunit": "creation_redemption_unit",
        "creationlimit": "creation_limit", "redemptionlimit": "redemption_limit",
        "maxcashratio": "max_cash_ratio", "recordnum": "record_num",
        "underlyingindex": "underlying_index", "navpercu": "nav_per_cu",
        "pbuid": "pbuid", "investoraccountid": "investor_account_id",
        "creationredemption": "creation_redemption",
        "creationredemptionmechanism": "creation_redemption_mechanism",
        "publish": "publish", "allcashflagstr": "all_cash_flag_str",
    },
}

BASKET_DECIMAL_COLS = frozenset({
    "number", "tdje", "sgtdje", "shtdje", "yjbl",
    "sg_yjbl", "sh_zjbl", "discount_rate", "premium_rate",
})
DAYINFO_DECIMAL_COLS = frozenset({
    "nav", "cash_component", "estimate_cash_component",
    "cash_dividend", "max_cash_ratio", "nav_per_cu",
})
DAYINFO_INT_COLS = frozenset({
    "creation_redemption_unit", "creation_limit", "redemption_limit", "record_num",
})


def _s(v) -> str | None:
    """去空白；空串 -> None。"""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _to_decimal(v) -> Decimal | None:
    s = _s(v)
    if s is None:
        return None
    try:
        return Decimal(s.replace(",", ""))  # 去千分位逗号（如 "1,000,000.00"）
    except InvalidOperation:
        return None


def _to_int(v) -> int | None:
    s = _s(v)
    if s is None:
        return None
    try:
        return int(Decimal(s.replace(",", "")))  # 去千分位，容错 "1000.0"/"1,000,000.00"
    except InvalidOperation:
        return None


def _to_date(v) -> date | None:
    s = _s(v)
    if s is None:
        return None
    fmt = "%Y-%m-%d" if "-" in s else "%Y%m%d"
    try:
        return datetime.strptime(s, fmt).date()
    except ValueError:
        return None


def _map_row(
    raw: dict,
    fmap: dict[str, str],
    decimal_cols: frozenset[str],
    int_cols: frozenset[str] = frozenset(),
) -> dict:
    """按映射表把一行 CSV-keyed dict 转成 DB-keyed dict（含类型转换）。"""
    out: dict = {}
    for csv_col, db_col in fmap.items():
        v = raw.get(csv_col)
        if db_col == "trading_day":
            out[db_col] = _to_date(v)
        elif db_col in decimal_cols:
            out[db_col] = _to_decimal(v)
        elif db_col in int_cols:
            out[db_col] = _to_int(v)
        else:
            out[db_col] = _s(v)
    return out


def ingest_basket(db: Session, source: str, raw_rows: Iterable[dict]) -> tuple[int, int]:
    """成份券入库。返回 (写入行数, 因主键缺失跳过行数)。

    按 (source, fund_code, trading_day) 先删后批量插，重抓幂等。
    主键四要素（source/fund_code/trading_day/stock_code）缺任一则跳过该行。
    """
    fmap = BASKET_FIELD_MAP.get(source)
    if fmap is None:
        raise ValueError(f"未知 PCF 数据源: {source}（请在 BASKET_FIELD_MAP 注册）")

    rows: list[dict] = []
    skipped = 0
    for raw in raw_rows:
        r = _map_row(raw, fmap, BASKET_DECIMAL_COLS)
        r["source"] = source
        if not (r.get("fund_code") and r.get("trading_day") and r.get("stock_code")):
            skipped += 1
            continue
        rows.append(r)

    if not rows:
        return 0, skipped

    keys = {(r["fund_code"], r["trading_day"]) for r in rows}
    try:
        for fc, td in keys:
            db.execute(
                delete(RawPcfBasket).where(
                    RawPcfBasket.source == source,
                    RawPcfBasket.fund_code == fc,
                    RawPcfBasket.trading_day == td,
                )
            )
        db.execute(insert(RawPcfBasket), rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows), skipped


def ingest_day_info(db: Session, source: str, raw_rows: Iterable[dict]) -> tuple[int, int]:
    """基金级头部入库。返回 (写入行数, 跳过行数)。幂等。

    该源若未在 DAYINFO_FIELD_MAP 注册（如 fsfund 无头部信息），静默返回 (0, 0)。
    """
    fmap = DAYINFO_FIELD_MAP.get(source)
    if fmap is None:
        return 0, 0

    rows: list[dict] = []
    skipped = 0
    for raw in raw_rows:
        r = _map_row(raw, fmap, DAYINFO_DECIMAL_COLS, DAYINFO_INT_COLS)
        r["source"] = source
        if not (r.get("fund_code") and r.get("trading_day")):
            skipped += 1
            continue
        rows.append(r)

    if not rows:
        return 0, skipped

    keys = {(r["fund_code"], r["trading_day"]) for r in rows}
    try:
        for fc, td in keys:
            db.execute(
                delete(RawPcfDayInfo).where(
                    RawPcfDayInfo.source == source,
                    RawPcfDayInfo.fund_code == fc,
                    RawPcfDayInfo.trading_day == td,
                )
            )
        db.execute(insert(RawPcfDayInfo), rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows), skipped
