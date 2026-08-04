"""PCF 联动衍生：ETF 申赎 → 成份股买卖压力估算。

把「份额变动（申赎结果）× PCF 篮子（申赎配方）× 最小申赎单位」折算成每只成份股
因当日净申赎被估算净买/净卖的股数与金额，把 etf_flow 的宏观份额信号下沉到成份股层面。

口径：
- ``net_units = shares_change(万份) × 10000 / creation_redemption_unit(份)`` —— 净申赎单位数
- ``est_shares = net_units × number`` —— 成份股估算买卖股数（带方向，正=净买/红、负=净卖/绿）
- ``est_amount = net_units × tdje`` —— 估算金额（PCF 替代金额近似；tdje 缺则空）
- 现金替代券（tdbz 含「现金」）标注类型、不剔除，但股数为配方含量而非实物流动
- 快照日取「最近同时有 PCF basket + 可用单位 + 连续两日份额」的交易日；basket 与单位同 source
"""

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.etf_share import RawEtfShareDaily
from ..models.pcf import RawPcfBasket, RawPcfDayInfo
from .etf_share_data import ensure_etf_shares
from .pcf_data import ensure_pcf_data
from .symbol_catalog import lookup_name

# 常见 ETF 最小申赎单位兜底（份）。仅对「无 PCF day_info」的源（如 fsfund）生效；
# 按各基金公告实际值校准/补充。
DEFAULT_CRU: dict[str, int] = {
    "510300": 900000,
    "510050": 900000,
    "510500": 900000,
    "510880": 900000,
    "159919": 900000,
    "512880": 1000000,
}

NOTE = (
    "估算口径：净申赎单位数 = 份额变动(万份)×10000 / 最小申赎单位；"
    "成份股估算买卖股数 = 单位数 × 配方数量；金额 = 单位数 × PCF 替代金额(近似)；"
    "现金替代券不计入实物股票流动。"
)


def _is_cash_substitute(row) -> bool:
    """判定成份券是否现金替代（非实物交收）。

    真实样本里 tdbz 取值各异（如「深市允许」「现金替代」「退订」等），此处宽松判定
    含「现金」字样即视为现金替代；可按实际样本在 ``BASKET_FIELD_MAP`` 对应源的字段微调。
    """
    return "现金" in str(row.tdbz or "")


def compute_pcf_pressure(db: Session, symbol: str) -> dict:
    """返回 ETF 申赎→成份股压力快照。结构见模块 docstring 与下方 base。"""
    name = lookup_name(symbol) or symbol
    base = {
        "symbol": symbol, "name": name, "available": False, "reason": None,
        "snapshot_day": None, "source": None, "creation_redemption_unit": None,
        "unit_source": None, "shares_change": None, "net_units": None,
        "direction": None, "items": [], "note": NOTE,
    }

    # 1) 保障数据（失败不阻断：库内可能已有历史数据）
    today = date.today()
    try:
        ensure_etf_shares(db, symbol, today - timedelta(days=200), today)
    except Exception:  # noqa: BLE001
        pass
    try:
        ensure_pcf_data(db, symbol)
    except Exception:  # noqa: BLE001
        pass

    # 2) PCF day_info 候选（有真实 creation_redemption_unit > 0）：trading_day -> (source, cru)
    di_rows = db.execute(
        select(
            RawPcfDayInfo.trading_day,
            RawPcfDayInfo.source,
            RawPcfDayInfo.creation_redemption_unit,
        )
        .where(RawPcfDayInfo.fund_code == symbol, RawPcfDayInfo.creation_redemption_unit > 0)
        .order_by(RawPcfDayInfo.trading_day.desc())
        .limit(60)
    ).all()
    di_map = {r[0]: (r[1], int(r[2])) for r in di_rows}

    # 3) basket 候选：trading_day -> [source, ...]
    bk_rows = db.execute(
        select(RawPcfBasket.trading_day, RawPcfBasket.source)
        .distinct()
        .where(RawPcfBasket.fund_code == symbol)
        .order_by(RawPcfBasket.trading_day.desc())
        .limit(60)
    ).all()
    bk_by_day: dict = {}
    for r in bk_rows:
        bk_by_day.setdefault(r[0], []).append(r[1])

    if not bk_by_day and not di_map:
        base["reason"] = "该 ETF 暂无 PCF 成份券数据"
        return base

    # 4) 份额变动可算的日期（升序，change_map[T] = fd_share[T] - fd_share[T-1]）
    sh_rows = db.execute(
        select(RawEtfShareDaily.trade_date, RawEtfShareDaily.fd_share)
        .where(RawEtfShareDaily.symbol == symbol)
        .order_by(RawEtfShareDaily.trade_date.asc())
        .limit(400)
    ).all()
    change_map: dict = {}
    for i in range(1, len(sh_rows)):
        change_map[sh_rows[i][0]] = sh_rows[i][1] - sh_rows[i - 1][1]
    if not change_map:
        base["reason"] = "无份额变动数据（需先有 ETF 份额落库）"
        return base

    # 5) 选快照日：basket ∪ day_info 中最近、有可用单位、能算份额变动、且 basket 同源存在的交易日
    candidate_dates = sorted(set(bk_by_day.keys()) | set(di_map.keys()), reverse=True)
    snapshot = None
    chosen_source = None
    cru = None
    unit_source = None
    for d in candidate_dates:
        if d not in change_map:
            continue
        if d in di_map:
            chosen_source, cru = di_map[d]
            unit_source = "day_info"
        elif symbol in DEFAULT_CRU and d in bk_by_day:
            chosen_source = bk_by_day[d][0]
            cru = DEFAULT_CRU[symbol]
            unit_source = "default"
        else:
            continue
        # 该 source 该日须有 basket 行
        if chosen_source in bk_by_day.get(d, []):
            snapshot = d
            break

    if snapshot is None or not cru or cru <= 0:
        base["reason"] = "缺少最小申赎单位（该源无 PCF 头部，且无默认值）或无匹配成份券"
        return base

    change = change_map[snapshot]
    net_units = change * Decimal(10000) / Decimal(cru)

    # 6) 取 basket 行（同 source 同日）
    basket = db.execute(
        select(RawPcfBasket)
        .where(
            RawPcfBasket.source == chosen_source,
            RawPcfBasket.fund_code == symbol,
            RawPcfBasket.trading_day == snapshot,
        )
    ).scalars().all()
    if not basket:
        base["reason"] = f"{chosen_source} 在 {snapshot} 无成份券行"
        return base

    items = []
    for row in basket:
        est_shares = round(float(net_units * row.number), 2) if row.number is not None else None
        est_amount = round(float(net_units * row.tdje), 2) if row.tdje is not None else None
        items.append({
            "stock_code": row.stock_code,
            "stock_short": row.stock_short,
            "number": float(row.number) if row.number is not None else None,
            "type": "现金替代" if _is_cash_substitute(row) else "实物",
            "est_shares": est_shares,
            "est_amount": est_amount,
        })
    def _amt(x):
        return abs(x["est_amount"]) if x["est_amount"] is not None else abs(x["est_shares"] or 0)

    items.sort(key=_amt, reverse=True)

    return {
        **base,
        "available": True,
        "snapshot_day": snapshot.isoformat(),
        "source": chosen_source,
        "creation_redemption_unit": cru,
        "unit_source": unit_source,
        "shares_change": round(float(change), 4),
        "net_units": round(float(net_units), 4),
        "direction": "subscription" if net_units > 0 else "redemption",
        "items": items,
    }
