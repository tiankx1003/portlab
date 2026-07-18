"""Roadmap 接口：返回 TASKS.md 中未实现任务（☐）。"""

from fastapi import APIRouter

from ..schemas.common import ApiResponse
from ..schemas.roadmap import Roadmap, RoadmapItem
from ..services.roadmap import get_roadmap

router = APIRouter()


@router.get("", response_model=ApiResponse)
def roadmap() -> ApiResponse:
    raw = get_roadmap()
    data = Roadmap(items=[RoadmapItem(**i) for i in raw["items"]], total=raw["total"])
    return ApiResponse.ok(data=data)
