"""A 股标的目录（代码-名称）缓存与查询，供标的搜索与名称解析复用。

名称解析必须稳定（图表标题依赖），因此：
- 进程启动时后台预热目录（warmup）；
- lookup_name 在目录未加载时**阻塞加载**（单飞），保证总能解析；
- 加载失败保留旧数据或空，不抛异常。
"""

import os
import threading
import time

os.environ.setdefault("TQDM_DISABLE", "1")  # 屏蔽 stock_info_a_code_name 的进度条

import akshare as ak

from ..utils.symbol import strip_market_prefix

_CACHE: dict[str, object] = {"data": None, "ts": 0.0}
_TTL = 6 * 3600  # 6 小时
_lock = threading.Lock()


def _ensure(refresh: bool = False) -> None:
    """单飞加载/刷新目录（A 股股票 + ETF）；失败时保留旧数据或空。"""
    with _lock:
        data = _CACHE["data"]
        stale = data is None or (refresh and time.time() - _CACHE["ts"] > _TTL)
        if not stale:
            return
        merged: list[dict] = []
        seen: set[str] = set()

        # A 股股票
        try:
            df = ak.stock_info_a_code_name()
            for _, r in df.iterrows():
                code = str(r["code"]).zfill(6)
                if code in seen:
                    continue
                seen.add(code)
                merged.append({"code": code, "name": str(r["name"]).strip(), "type": "stock"})
        except Exception:
            pass

        # ETF（sina 源，代码带 sh/sz 前缀）
        try:
            df = ak.fund_etf_category_sina(symbol="ETF基金")
            for _, r in df.iterrows():
                code = strip_market_prefix(str(r["代码"]))
                if not code or code in seen:
                    continue
                seen.add(code)
                merged.append({"code": code, "name": str(r["名称"]).strip(), "type": "etf"})
        except Exception:
            pass

        if merged:
            _CACHE["data"] = merged
            _CACHE["ts"] = time.time()


def warmup() -> None:
    """启动时后台预热目录。"""
    _ensure(refresh=True)


def get_symbol_list() -> list[dict]:
    """获取（并按 TTL 刷新）A 股代码-名称列表。"""
    _ensure(refresh=True)
    return _CACHE["data"] or []


def lookup_name(symbol: str) -> str:
    """根据标的代码查名称。

    目录未加载时**阻塞加载**（单飞），保证总能解析；列表中查不到（如 ETF/指数）
    返回空串，由调用方回退为代码。
    """
    if _CACHE["data"] is None:
        _ensure(refresh=False)
    data = _CACHE["data"]
    code = strip_market_prefix(symbol)
    if not data:
        return ""
    for it in data:
        if it["code"] == code:
            return it["name"]
    return ""
