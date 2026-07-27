"""HTTP 桥接层：单例 httpx.AsyncClient + 统一解包 PortLab ApiResponse 信封。

- 成功（code == 0）：返回 ``data``。
- 业务错误（code != 0）：抛 ``ValueError``，把 backend 的中文 message 透传给 LLM。
- 网络错误（backend 宕机）：抛 httpx 原始异常，由 FastMCP 转 tool error。
"""

from __future__ import annotations

from typing import Any

import httpx


class PortLabAPIError(ValueError):
    """backend 返回 code != 0 时的业务错误，message 直接给 LLM。"""


class PortLabClient:
    """单例 HTTP client，统一解包 ``{code, message, data}`` 信封。"""

    def __init__(self, base_url: str, *, timeout: float = 60.0):
        # timeout=60 覆盖 /event/{id}/impact（拉多标的行情）与回测创建的拉数延迟。
        self._http = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """调 backend，返回 ApiResponse.data；code != 0 抛 PortLabAPIError。"""
        try:
            r = await self._http.request(method, path, params=params, json=json)
        except httpx.RequestError as e:
            raise PortLabAPIError(
                f"PortLab 后端不可达（{e.__class__.__name__}）。"
                "请确认 backend 已启动：docker compose up backend。"
            ) from e
        r.raise_for_status()
        try:
            payload = r.json()
        except ValueError as e:
            raise PortLabAPIError(f"backend 返回非 JSON：HTTP {r.status_code}") from e
        if payload.get("code") != 0:
            raise PortLabAPIError(f"PortLab API 错误：{payload.get('message', '未知错误')}")
        return payload.get("data")

    async def close(self) -> None:
        await self._http.aclose()
