"""PCF 数据保障（按需懒加载，仿 ``ensure_price_data`` / ``ensure_etf_shares``）。

点击加载时确保该 ETF 的 PCF 在库且新鲜，免去手动跑爬虫：

- **已知 source + 新鲜**（最近 ``trading_day`` ≥ today − ``FRESH_DAYS``）→ 跳过。
- **已知 source + 过期** → 补抓 ``(最近日, today]`` 并入库。
- **未知 source（库里无）** → 按 ``pcf_crawlers.SOURCES`` 优先级，每个 source 抓最近
  ``DISCOVER_DAYS`` 天试探；任一 source 命中（basket 非空）即定为该 source 并入库。
  全自动发现，无需维护「ETF→基金公司」映射；入库后库记 source，后续走已知 source 快路径。
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.pcf import RawPcfBasket
from .pcf_crawlers import SOURCES, fetch_pcf_day
from .pcf_ingest import ingest_basket, ingest_day_info

logger = logging.getLogger(__name__)

FRESH_DAYS = 3  # 最近 trading_day 在此之内视为新鲜，不补抓（覆盖周末）
DISCOVER_DAYS = 5  # 未知 source 时每个源试探的最近日历天数


def _fetch_and_ingest(db: Session, source: str, symbol: str, start: date, end: date) -> str | None:
    """抓 [start, end] 该 source+symbol 的 PCF 并入库。返回 None（有数据并入库）或错误串。"""
    basket_rows: list[dict] = []
    day_info_rows: list[dict] = []
    d = start
    while d <= end:
        try:
            r = fetch_pcf_day(source, symbol, d)
        except Exception as e:  # noqa: BLE001 — 单日失败跳过，不中断
            logger.info("PCF 抓取失败 %s %s %s: %s", source, symbol, d, e)
            d += timedelta(days=1)
            continue
        basket_rows.extend(r["basket_rows"])
        if r["day_info_row"]:
            day_info_rows.append(r["day_info_row"])
        d += timedelta(days=1)

    if not basket_rows:
        return f"{source} 在 {start}~{end} 无 PCF 数据"
    ingest_basket(db, source, basket_rows)
    if day_info_rows:
        ingest_day_info(db, source, day_info_rows)
    return None


def ensure_pcf_data(db: Session, symbol: str) -> str | None:
    """确保 symbol 的 PCF 在库且新鲜。返回错误信息或 None（None=已就绪或补齐成功）。"""
    today = date.today()

    # 已知 source + 最近 trading_day（取最近者）
    row = db.execute(
        select(RawPcfBasket.source, func.max(RawPcfBasket.trading_day))
        .where(RawPcfBasket.fund_code == symbol)
        .group_by(RawPcfBasket.source)
        .order_by(func.max(RawPcfBasket.trading_day).desc())
        .limit(1)
    ).one_or_none()

    if row:
        source, max_day = row[0], row[1]
        if max_day >= today - timedelta(days=FRESH_DAYS):
            return None  # 新鲜
        return _fetch_and_ingest(db, source, symbol, max_day + timedelta(days=1), today)

    # 未知 source：按优先级自动发现
    start = today - timedelta(days=DISCOVER_DAYS - 1)
    for source in SOURCES:
        err = _fetch_and_ingest(db, source, symbol, start, today)
        if err is None:
            return None  # 命中并入库
    return "无可用的 PCF 数据源（该 ETF 非已支持的基金公司，或抓取失败）"
