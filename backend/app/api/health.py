"""健康检查端点。不依赖数据库，仅表明服务存活。"""

from fastapi import APIRouter

from ..schemas.common import ApiResponse

router = APIRouter()


@router.get("/health", response_model=ApiResponse)
def health() -> ApiResponse:
    return ApiResponse.ok(data={"status": "ok"})
