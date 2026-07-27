"""tool 共用小工具：GET/POST 入参清洗 + 降采样应用。"""

from __future__ import annotations

from typing import Any

from ..client import PortLabClient
from ..config import settings
from ..transforms import apply_sample


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


async def _get(client: PortLabClient, path: str, params: dict[str, Any] | None = None) -> Any:
    return await client.call("GET", path, params=_clean(params or {}))


async def _post(client: PortLabClient, path: str, body: dict[str, Any]) -> Any:
    return await client.call("POST", path, json=_clean(body))


async def _sampled(
    client: PortLabClient,
    path: str,
    sample: str,
    params: dict[str, Any] | None = None,
) -> Any:
    """GET 并按 sample 策略降采样（chart80 / event_impact）。"""
    data = await client.call("GET", path, params=_clean(params or {}))
    return apply_sample(data, sample, settings.mcp_chart_target_points)
