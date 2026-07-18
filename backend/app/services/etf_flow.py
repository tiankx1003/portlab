"""ETF 资金流向三信号（017）—— 全部基于 Tushare Pro。

三信号：
- ``shares_change``：ETF 每日份额变动（``fund_share.fd_share`` 环比差，万份）。
  份额持续增加而价格平淡 ⇒ 机构/国家队逢低吸筹（核心观察信号）。
- ``northbound``：北向资金每日净流入（``moneyflow_hsgt.north_money``，万元）。
- ``main_flow``：主力资金净流入。Tushare ``moneyflow`` 仅覆盖**个股**、ETF 返回空，
  故对 ETF 该信号置 ``available=False`` 并说明（如需可换为成分股聚合）。

Token 解析复用 TushareFetcher 的优先级（DB → 环境变量）；数据源开关关闭或未配置 Token
则整体降级。
"""

import logging
from datetime import date

from ..services.fetcher.tushare_fetcher import _resolve_token, _to_tushare_code
from ..services.symbol_catalog import lookup_name

logger = logging.getLogger(__name__)

# 前端展示窗口（最近 N 个交易日）
_WINDOW = 180


def _to_iso(yyyymmdd: str) -> str:
    s = str(yyyymmdd)
    return f"{s[:4]}-{s[4:6]}-{s[6:8]}" if len(s) == 8 else s


def _signal_ok(dates: list[str], values: list[float]) -> dict:
    return {"available": True, "dates": dates, "values": values}


def _signal_fail(reason: str) -> dict:
    return {"available": False, "reason": reason, "dates": [], "values": []}


def get_etf_flow(symbol: str, start: date | None = None, end: date | None = None) -> dict:
    name = lookup_name(symbol) or symbol
    try:
        token = _resolve_token()
    except Exception as e:  # noqa: BLE001
        return {
            "symbol": symbol, "name": name, "available": False,
            "reason": str(e), "signals": {},
        }

    try:
        import tushare as ts  # noqa: PLC0415
    except ImportError as e:  # noqa: BLE001
        return {"symbol": symbol, "name": name, "available": False,
                "reason": f"未安装 tushare：{e}", "signals": {}}

    ts.set_token(token)
    pro = ts.pro_api()
    code = _to_tushare_code(symbol)
    sd = (start or date(2000, 1, 1)).strftime("%Y%m%d")
    ed = (end or date.today()).strftime("%Y%m%d")

    signals: dict[str, dict] = {}

    # 1) 份额变动（fund_share: fd_share 万份，按交易日升序后取环比差）
    try:
        df = pro.fund_share(ts_code=code, start_date=sd, end_date=ed)
        if df is None or len(df) == 0:
            signals["shares_change"] = _signal_fail("无份额数据")
        else:
            df = df.sort_values("trade_date")
            d = df["trade_date"].tolist()[-_WINDOW:]
            sh = df["fd_share"].astype(float).tolist()[-_WINDOW:]
            change = [round(sh[i] - sh[i - 1], 2) if i > 0 else 0.0 for i in range(len(sh))]
            signals["shares_change"] = _signal_ok([_to_iso(x) for x in d], change)
    except Exception as e:  # noqa: BLE001
        signals["shares_change"] = _signal_fail(f"份额接口失败：{type(e).__name__}: {str(e)[:80]}")

    # 2) 北向资金净流入（moneyflow_hsgt: north_money 万元）
    try:
        df = pro.moneyflow_hsgt(start_date=sd, end_date=ed)
        if df is None or len(df) == 0:
            signals["northbound"] = _signal_fail("无北向数据")
        else:
            df = df.sort_values("trade_date")
            d = df["trade_date"].tolist()[-_WINDOW:]
            v = [round(float(x), 2) for x in df["north_money"].tolist()[-_WINDOW:]]
            signals["northbound"] = _signal_ok([_to_iso(x) for x in d], v)
    except Exception as e:  # noqa: BLE001
        signals["northbound"] = _signal_fail(
            f"北向接口失败（可能积分不足）：{type(e).__name__}: {str(e)[:60]}"
        )

    # 3) 主力资金净流入（moneyflow 仅个股；ETF 返回空 → 降级）
    try:
        df = pro.moneyflow(ts_code=code, start_date=sd, end_date=ed)
        if df is None or len(df) == 0:
            signals["main_flow"] = _signal_fail(
                "Tushare moneyflow 仅覆盖个股，ETF 无主力资金流向；"
                "可用份额变动 + 北向观察机构动向"
            )
        else:
            df = df.sort_values("trade_date")
            d = df["trade_date"].tolist()[-_WINDOW:]
            v = [round(float(x), 2) for x in df["net_mf_amount"].tolist()[-_WINDOW:]]
            signals["main_flow"] = _signal_ok([_to_iso(x) for x in d], v)
    except Exception as e:  # noqa: BLE001
        signals["main_flow"] = _signal_fail(
            f"主力接口失败：{type(e).__name__}: {str(e)[:55]}"
        )

    any_ok = any(s.get("available") for s in signals.values())
    return {
        "symbol": symbol,
        "name": name,
        "available": any_ok,
        "as_of": next((s["dates"][-1] for s in signals.values() if s.get("available") and s["dates"]), None),
        "signals": signals,
    }
