"""估值温度计接口（016）。GET /api/valuation?symbol=000300。"""

from fastapi import APIRouter

from ..schemas.common import ApiResponse
from ..services.valuation import get_valuation

router = APIRouter()


@router.get("", response_model=ApiResponse)
def valuation(symbol: str = "000300") -> ApiResponse:
    """指数 PE 历史分位 / 温度。数据源不可用时 available=False。"""
    return ApiResponse.ok(data=get_valuation(symbol))
