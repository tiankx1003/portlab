"""PCF 联动：ETF 申赎→成份股压力。GET /api/pcf-pressure?symbol=510880。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.common import ApiResponse
from ..services.pcf_pressure import compute_pcf_pressure

router = APIRouter()


@router.get("", response_model=ApiResponse)
def pcf_pressure(symbol: str = "510880", db: Session = Depends(get_db)) -> ApiResponse:
    """ETF 申赎→成份股买卖压力估算（份额变动 × PCF 篮子 × 最小申赎单位）。"""
    return ApiResponse.ok(data=compute_pcf_pressure(db, symbol))
