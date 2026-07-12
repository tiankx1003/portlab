"""标的搜索接口（A 股代码/名称）。基于 akshare 的 A 股列表，内存缓存。"""

import os
import time

os.environ.setdefault("TQDM_DISABLE", "1")  # 屏蔽 stock_info_a_code_name 的进度条

import akshare as ak
from fastapi import APIRouter, Query

from ..schemas.backtest import SymbolItem
from ..schemas.common import ApiResponse

router = APIRouter()

_CACHE: dict[str, object] = {"data": None, "ts": 0.0}
_TTL = 6 * 3600  # 6 小时缓存


def _load_symbol_list() -> list[SymbolItem]:
    df = ak.stock_info_a_code_name()
    return [
        SymbolItem(code=str(r["code"]).zfill(6), name=str(r["name"]).strip(), type="stock")
        for _, r in df.iterrows()
    ]


def _get_symbol_list() -> list[SymbolItem]:
    now = time.time()
    if _CACHE["data"] is None or now - _CACHE["ts"] > _TTL:
        try:
            _CACHE["data"] = _load_symbol_list()
            _CACHE["ts"] = now
        except Exception:
            pass  # 拉取失败时保留旧缓存（或空）
    return _CACHE["data"] or []


@router.get("/search", response_model=ApiResponse)
def search(q: str = Query(..., min_length=1, description="按代码或名称模糊搜索")) -> ApiResponse:
    keyword = q.strip()
    items = _get_symbol_list()
    hits = [it for it in items if keyword in it.code or keyword in it.name][:30]
    return ApiResponse.ok(data=hits)
