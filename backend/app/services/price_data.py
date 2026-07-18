"""行情数据保障（DCA / MA120 回测共用）。

确保 [start, end] 区间行情完整：已覆盖则跳过；缺前段/后段则补拉对应子区间。
旧实现仅判 count==0 会把"部分覆盖"误判为完整，这里按 MIN/MAX 判定并补缺段。

数据源由 ``resolve_source(db)`` 决定：开关开启且 Token 有效 → 走 Tushare，查 / 写
``raw_price_daily_tushare``；否则走 AkShare，查 / 写 ``raw_price_daily``。两源各自
「先查本地表 → 仅补缺失区间 → UPSERT 写回」，互不污染、不重复拉取。
"""

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .fetcher import FetchError, get_fetcher
from .fetcher.registry import SOURCE_TABLE, resolve_source
from .storage import upsert_bars

logger = logging.getLogger(__name__)

# 起点端允许的假期偏差：MIN 比 start 晚不超过此值视为已覆盖（避免春节等假期误判为缺数据）
FRONT_TOL = timedelta(days=7)


def ensure_price_data(db: Session, symbol: str, start: date, end: date) -> str | None:
    """确保 [start, end] 区间行情完整。返回错误信息或 None（None 表示已覆盖或补齐成功）。"""
    src = resolve_source(db)
    model = SOURCE_TABLE[src]
    fetcher = get_fetcher(src)

    row = db.execute(
        select(
            func.min(model.trade_date),
            func.max(model.trade_date),
            func.count(),
        )
        .select_from(model)
        .where(
            model.symbol == symbol,
            model.trade_date >= start,
            model.trade_date <= end,
        )
    ).one()
    mn, mx, cnt = row[0], row[1], row[2]

    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    else:
        if mn > start + FRONT_TOL:
            ranges.append((start, mn))  # 前段缺失：拉到已有最早日（含，UPSERT 幂等）
        if mx < end:
            ranges.append((mx, end))  # 后段缺失 / 有新数据：从已有最晚日（含）拉到 end

    if not ranges:
        return None  # 区间已覆盖，无需拉取

    for s, e in ranges:
        try:
            bars = fetcher.fetch_daily(symbol, s, e)
        except FetchError as ex:
            return f"数据缺失且自动拉取失败（{symbol} {s}~{e}）：{ex}"
        except Exception as ex:  # noqa: BLE001
            return f"数据缺失且自动拉取失败（{symbol} {s}~{e}）：{ex}"

        if bars:
            upsert_bars(db, bars, model=model)
        else:
            logger.info("%s 在 %s~%s 无可拉取行情（可能为未来日期或已退市）", symbol, s, e)
    return None
