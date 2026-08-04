"""PCF 爬虫核心（华宝 fsfund + 华泰柏瑞 huatai_pb）—— CLI 与按需懒加载共用。

``fetch_pcf_day(source, fund_code, day)`` 统一返回 ``{basket_rows, day_info_row, ...}``，
结构直接喂 ``app.services.pcf_ingest``。两家接口的签名/请求/解析逻辑集中于此（单一真相），
CLI 脚本（``scripts/pcf/``）与 ``pcf_data.ensure_pcf_data`` 共用，避免重复。

- huatai_pb：POST 表单、无签名、返回 ``stockList`` + ``dayInfo``，``tradingday`` 为毫秒戳。
- fsfund：POST JSON、MD5 ``addSignature`` 签名、返回 ``data`` 数组（仅篮子，无头部）。
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

# 自动发现时的尝试优先级（华泰柏瑞覆盖面广，优先）
SOURCES = ["huatai_pb", "fsfund"]

# ============================ huatai_pb（华泰柏瑞）============================
HUATAI_API = "https://www.huatai-pb.com/etf-web/etf/index.json"
HUATAI_SITE = "https://www.huatai-pb.com"
HUATAI_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36 Edg/150.0.0.0"
)
_CST = timezone(timedelta(hours=8))  # 东八区，tradingday 毫秒戳转日期

HUATAI_BASKET_COLUMNS = [
    "fundCode", "fundCodes", "fundName", "tradingDay",
    "fundId", "stockCode", "stockShort", "gpsc", "stockCodesrc",
    "number", "tdje", "sgtdje", "shtdje",
    "yjbl", "discountrate", "premiumrate", "tdbz", "buyorsell",
]
HUATAI_BASKET_CN = {
    "fundCode": "基金代码", "fundCodes": "操作代码", "fundName": "基金简称",
    "tradingDay": "交易日期", "fundId": "成份券基金ID", "stockCode": "股票代码",
    "stockShort": "股票简称", "gpsc": "股票市场", "stockCodesrc": "股票代码来源",
    "number": "数量(股)", "tdje": "替代金额", "sgtdje": "申购替代金额",
    "shtdje": "赎回替代金额", "yjbl": "溢价比例(%)", "discountrate": "现金替代折价率(%)",
    "premiumrate": "现金替代溢价比例(%)", "tdbz": "替代标志", "buyorsell": "买卖标志",
}
HUATAI_DAYINFO_COLUMNS = [
    "fundCode", "fundName", "tradingDay",
    "nav", "cashcomponent", "estimatecashcomponent", "cashdividend",
    "creationredemptionunit", "creationlimit", "redemptionlimit",
    "maxcashratio", "recordnum", "underlyingindex", "navpercu",
    "pbuid", "investoraccountid",
    "creationredemption", "creationredemptionmechanism",
    "publish", "allcashflagstr",
]
HUATAI_DAYINFO_CN = {
    "fundCode": "基金代码", "fundName": "基金简称", "tradingDay": "交易日期",
    "nav": "基金净值", "cashcomponent": "现金差额", "estimatecashcomponent": "预估现金差额",
    "cashdividend": "现金红利", "creationredemptionunit": "最小申赎单位(份)",
    "creationlimit": "申购上限", "redemptionlimit": "赎回上限",
    "maxcashratio": "最大现金替代比例(%)", "recordnum": "成份券数量",
    "underlyingindex": "标的指数", "navpercu": "单位净值(对价)",
    "pbuid": "PBU编号", "investoraccountid": "投资者账户ID",
    "creationredemption": "申赎标志", "creationredemptionmechanism": "申赎机制",
    "publish": "发布标志", "allcashflagstr": "全现金标志",
}
# 篮子列名 -> stockList 内原始 JSON key（接口返回全小写）
_HUATAI_STOCK_KEY = {
    "fundId": "fundid", "stockCode": "stockcode", "stockShort": "stockshort",
    "gpsc": "gpsc", "stockCodesrc": "stockcodesrc", "number": "number",
    "tdje": "tdje", "sgtdje": "sgtdje", "shtdje": "shtdje", "yjbl": "yjbl",
    "discountrate": "discountrate", "premiumrate": "premiumrate",
    "tdbz": "tdbz", "buyorsell": "buyorsell",
}


def _ms_to_date(ms) -> str:
    """tradingday 毫秒戳 -> YYYY-MM-DD（东八区）。"""
    return datetime.fromtimestamp(int(ms) / 1000, tz=_CST).strftime("%Y-%m-%d")


def _huatai_fetch(fund_code, day_dash, *, retries, delay, cookie=None) -> dict:
    """POST 单个 (fundcode, beginDate=YYYY-MM-DD)，返回完整响应 dict（含 stockList/dayInfo）。"""
    body = urllib.parse.urlencode({"fundcode": fund_code, "beginDate": day_dash}).encode("utf-8")
    headers = {
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": HUATAI_SITE,
        "Referer": f"{HUATAI_SITE}/products/zhishu/{fund_code}/index.html",
        "User-Agent": HUATAI_UA,
        "X-Requested-With": "XMLHttpRequest",
    }
    if cookie:
        headers["Cookie"] = f"insert_cookie={cookie}"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(HUATAI_API, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
            obj = json.loads(raw.decode("utf-8"))
            if obj.get("status") == "success":
                return obj
            raise RuntimeError(f"接口返回 status={obj.get('status')} msg={obj.get('msg')}")
        except (
            urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, RuntimeError, json.JSONDecodeError,
        ) as e:
            last_err = e
            if attempt < retries:
                time.sleep(delay * attempt)
    raise RuntimeError(f"请求失败 {fund_code} {day_dash}: {last_err}")


def _huatai_basket_row(fund_code, trading_day, fund_name, fund_codes, item) -> dict:
    row = {col: "" for col in HUATAI_BASKET_COLUMNS}
    row["fundCode"] = fund_code
    row["fundCodes"] = fund_codes or ""
    row["fundName"] = fund_name or ""
    row["tradingDay"] = trading_day
    for col, key in _HUATAI_STOCK_KEY.items():
        v = item.get(key)
        row[col] = "" if v is None else str(v)
    return row


def _huatai_dayinfo_row(fund_code, trading_day, fund_name, day_info) -> dict:
    row = {col: "" for col in HUATAI_DAYINFO_COLUMNS}
    row["fundCode"] = fund_code
    row["fundName"] = fund_name or ""
    row["tradingDay"] = trading_day
    for col in HUATAI_DAYINFO_COLUMNS:
        if col in ("fundCode", "fundName", "tradingDay"):
            continue
        v = day_info.get(col)
        row[col] = "" if v is None else str(v)
    return row


# ============================ fsfund（华宝）============================
FSFUND_API = "https://api.fsfund.com/v2/webzk/queryController/getFundShareInfo"
FSFUND_SIGN_KEY = "CD364559FDA24D53B05F01E943ECDFCC"
FSFUND_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
)

FSFUND_BASKET_COLUMNS = [
    "fundCode", "tradingDay", "id", "fundId", "scid",
    "stockCode", "stockShort", "number",
    "tdbz", "tdje", "sgtdje", "shtdje",
    "yjbl", "sgyjbl", "shzjbl",
    "gpsc", "stockCodesrc", "mmbz", "reserved", "procFlag",
]
FSFUND_BASKET_CN = {
    "fundCode": "基金代码", "tradingDay": "交易日期", "id": "记录ID", "fundId": "基金ID",
    "scid": "市场ID", "stockCode": "股票代码", "stockShort": "股票简称", "number": "数量(股)",
    "tdbz": "退订标志", "tdje": "退订金额", "sgtdje": "申购退订金额", "shtdje": "赎回退订金额",
    "yjbl": "应交比例", "sgyjbl": "申购应交比例", "shzjbl": "赎回资金比例",
    "gpsc": "股票市场", "stockCodesrc": "股票代码来源", "mmbz": "买卖标志",
    "reserved": "保留字段", "procFlag": "处理标志",
}


def _fsfund_signature(params: dict) -> str:
    """复刻前端 addSignature 的 MD5 签名。"""
    clean = {}
    for k, v in params.items():
        if v is None or v == "" or v == "null":
            continue
        clean[k] = str(v)
    clean.pop("signature", None)
    sign_str = "".join(f"{k}={clean[k]}&" for k in sorted(clean.keys()))
    sign_str += f"key={FSFUND_SIGN_KEY}"
    return hashlib.md5(sign_str.encode("utf-8")).hexdigest()


def _fsfund_fetch(fund_code, day_compact, *, retries, delay) -> list:
    """POST 单个 (fundCode, startDate=YYYYMMDD)，返回 data 数组（可能为空）。"""
    ts = str(int(time.time() * 1000))
    params = {"fundCode": fund_code, "netNo": "web", "timestamp": ts, "startDate": day_compact}
    params["signature"] = _fsfund_signature(params)
    body = json.dumps(params).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Origin": "https://www.fsfund.com",
        "Referer": "https://www.fsfund.com/",
        "User-Agent": FSFUND_UA,
        "netNo": "web",
    }
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(FSFUND_API, data=body, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read()
            obj = json.loads(raw.decode("utf-8"))
            if obj.get("code") == "0000":
                return obj.get("data") or []
            raise RuntimeError(f"接口返回 code={obj.get('code')} message={obj.get('message')}")
        except (
            urllib.error.URLError, urllib.error.HTTPError,
            TimeoutError, RuntimeError, json.JSONDecodeError,
        ) as e:
            last_err = e
            if attempt < retries:
                time.sleep(delay * attempt)
    raise RuntimeError(f"请求失败 {fund_code} {day_compact}: {last_err}")


def _fsfund_basket_row(fund_code, item) -> dict:
    row = {col: "" for col in FSFUND_BASKET_COLUMNS}
    for col in FSFUND_BASKET_COLUMNS:
        if col == "fundCode":
            row[col] = fund_code
        else:
            v = item.get(col)
            row[col] = "" if v is None else str(v)
    return row


# ============================ 统一接口 ============================
def _to_date(day) -> date:
    if isinstance(day, date):
        return day
    s = str(day)
    return datetime.strptime(s, "%Y-%m-%d" if "-" in s else "%Y%m%d").date()


def fetch_pcf_day(source, fund_code, day, *, retries=3, delay=0.3, cookie=None) -> dict:
    """抓单只 ETF 单日 PCF，返回统一结构（无数据时 basket_rows 为空列表）。

    day: date 对象或 YYYY-MM-DD / YYYYMMDD 字符串（内部按源适配格式）。
    返回: {basket_rows, day_info_row, fund_name, fund_codes, trading_day}，
    basket_rows / day_info_row 均为「CSV 列名键」dict，可直接喂 pcf_ingest。
    请求失败抛 RuntimeError（由调用方 try/except）。
    """
    d = _to_date(day)
    if source == "huatai_pb":
        day_dash = d.strftime("%Y-%m-%d")
        obj = _huatai_fetch(fund_code, day_dash, retries=retries, delay=delay, cookie=cookie)
        fund_name = obj.get("fundname") or ""
        fund_codes = obj.get("fundcodes") or ""
        stock_list = obj.get("stockList") or []
        day_info = obj.get("dayInfo") or {}
        td_ms = stock_list[0].get("tradingday") if stock_list else None
        trading_day = _ms_to_date(td_ms) if td_ms else (obj.get("maxDate") or day_dash)
        basket_rows = [
            _huatai_basket_row(fund_code, trading_day, fund_name, fund_codes, it)
            for it in stock_list
        ]
        day_info_row = (
            _huatai_dayinfo_row(fund_code, trading_day, fund_name, day_info)
            if day_info else None
        )
        return {
            "basket_rows": basket_rows, "day_info_row": day_info_row,
            "fund_name": fund_name, "fund_codes": fund_codes, "trading_day": trading_day,
        }
    if source == "fsfund":
        day_compact = d.strftime("%Y%m%d")
        data = _fsfund_fetch(fund_code, day_compact, retries=retries, delay=delay)
        basket_rows = []
        for item in data:
            row = _fsfund_basket_row(fund_code, item)
            if not row["tradingDay"]:
                row["tradingDay"] = day_compact
            basket_rows.append(row)
        return {
            "basket_rows": basket_rows, "day_info_row": None,
            "fund_name": "", "fund_codes": "", "trading_day": day_compact,
        }
    raise ValueError(f"未知 PCF source: {source}")
