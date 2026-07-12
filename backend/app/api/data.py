"""数据拉取接口。"""

from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..schemas.common import ApiResponse
from ..services.fetcher import FetchError, get_fetcher
from ..services.storage import upsert_bars

router = APIRouter()


class FetchRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=32, description="标的代码，如 000001")
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _validate_dates(self) -> "FetchRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date 不能晚于 end_date")
        return self


class FetchResultData(BaseModel):
    symbol: str
    start_date: date
    end_date: date
    rows_upserted: int
    first_date: date | None = None
    last_date: date | None = None


@router.post("/fetch", response_model=ApiResponse)
def fetch_prices(req: FetchRequest, db: Session = Depends(get_db)) -> ApiResponse:
    """触发数据拉取并写入 raw_price_daily（增量 UPSERT，重复拉取不产生重复）。"""
    try:
        fetcher = get_fetcher(settings.data_source)
        bars = fetcher.fetch_daily(req.symbol, req.start_date, req.end_date)
    except FetchError as e:
        return ApiResponse.error(message=str(e))
    except Exception as e:  # noqa: BLE001
        return ApiResponse.error(message=f"数据拉取失败: {e}")

    rows_upserted = upsert_bars(db, bars)
    first_date = bars[0].trade_date if bars else None
    last_date = bars[-1].trade_date if bars else None

    return ApiResponse.ok(
        data=FetchResultData(
            symbol=req.symbol,
            start_date=req.start_date,
            end_date=req.end_date,
            rows_upserted=rows_upserted,
            first_date=first_date,
            last_date=last_date,
        )
    )
