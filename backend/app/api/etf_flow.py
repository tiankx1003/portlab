"""ETF 资金流向接口（017，Tushare 数据）。GET /api/etf-flow?symbol=510880&start=&end=。"""

from datetime import date

from fastapi import APIRouter

from ..schemas.common import ApiResponse
from ..services.etf_flow import get_etf_flow

router = APIRouter()


@router.get("", response_model=ApiResponse)
def etf_flow(
    symbol: str = "510880",
    start: date | None = None,
    end: date | None = None,
) -> ApiResponse:
    """ETF 份额变动 / 北向 / 主力 三信号（Tushare）。逐信号 available，ETF 主力降级。"""
    return ApiResponse.ok(data=get_etf_flow(symbol, start, end))
