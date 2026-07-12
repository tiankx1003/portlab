"""标的搜索接口（A 股代码/名称），数据来自 symbol_catalog 缓存。"""

from fastapi import APIRouter, Query

from ..schemas.common import ApiResponse
from ..services.symbol_catalog import get_symbol_list

router = APIRouter()


@router.get("/search", response_model=ApiResponse)
def search(q: str = Query(..., min_length=1, description="按代码或名称模糊搜索")) -> ApiResponse:
    keyword = q.strip()
    items = get_symbol_list()
    hits = [
        {"code": it["code"], "name": it["name"], "type": it.get("type", "stock")}
        for it in items
        if keyword in it["code"] or keyword in it["name"]
    ][:30]
    return ApiResponse.ok(data=hits)
