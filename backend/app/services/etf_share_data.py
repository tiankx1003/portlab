"""ETF 份额数据保障（PCF 联动用）。

确保 [start, end] 区间 ``raw_etf_share_daily`` 完整：已覆盖则跳过；缺前/后段则补拉
Tushare ``fund_share``（仿 ``price_data.ensure_price_data`` 的 MIN/MAX 缺口判定）。

与 ``etf_flow.py`` 解耦：实时三信号看板仍走纯 Tushare（零回归），份额落库由
PCF 联动链路（``pcf_pressure``）按需触发，使成份股压力分析不依赖用户事先看过流向。
"""

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models.etf_share import RawEtfShareDaily
from .fetcher import FetchError
from .fetcher.tushare_fetcher import _resolve_token, _to_tushare_code
from .storage import upsert_etf_shares

logger = logging.getLogger(__name__)

# 起点端假期偏差容忍（避免春节等误判为缺数据）
FRONT_TOL = timedelta(days=7)


def ensure_etf_shares(db: Session, symbol: str, start: date, end: date) -> str | None:
    """确保 [start, end] ETF 份额完整。返回错误信息或 None（None=已覆盖或补齐成功）。"""
    row = db.execute(
        select(
            func.min(RawEtfShareDaily.trade_date),
            func.max(RawEtfShareDaily.trade_date),
            func.count(),
        )
        .select_from(RawEtfShareDaily)
        .where(
            RawEtfShareDaily.symbol == symbol,
            RawEtfShareDaily.trade_date >= start,
            RawEtfShareDaily.trade_date <= end,
        )
    ).one()
    mn, mx, cnt = row[0], row[1], row[2]

    ranges: list[tuple[date, date]] = []
    if cnt == 0:
        ranges.append((start, end))
    else:
        if mn > start + FRONT_TOL:
            ranges.append((start, mn))  # 前段缺失（含，UPSERT 幂等）
        if mx < end:
            ranges.append((mx, end))  # 后段缺失/有新数据（含）

    if not ranges:
        return None  # 区间已覆盖

    try:
        token = _resolve_token()
    except FetchError as ex:
        return f"解析 Tushare Token 失败：{ex}"

    try:
        import tushare as ts  # noqa: PLC0415
    except ImportError as ex:  # noqa: BLE001
        return f"未安装 tushare：{ex}"

    ts.set_token(token)
    pro = ts.pro_api()
    code = _to_tushare_code(symbol)  # 510880 → 510880.SH

    for s, e in ranges:
        try:
            df = pro.fund_share(
                ts_code=code,
                start_date=s.strftime("%Y%m%d"),
                end_date=e.strftime("%Y%m%d"),
            )
        except Exception as ex:  # noqa: BLE001
            return f"拉取份额失败（{symbol} {s}~{e}）：{ex}"

        if df is None or len(df) == 0:
            logger.info("%s 在 %s~%s 无份额数据（可能为未来日期）", symbol, s, e)
            continue

        rows = [
            {
                "symbol": symbol,  # 落库用裸代码，与 raw_price_daily 一致便于跨表 join
                "trade_date": datetime.strptime(str(r["trade_date"]), "%Y%m%d").date(),
                "fd_share": str(r["fd_share"]),
                "source": "tushare",
            }
            for _, r in df.iterrows()
        ]
        upsert_etf_shares(db, rows)
    return None
