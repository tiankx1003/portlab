"""MCP 状态接口（026 Part C）：供前端状态面板探测 mcp 容器。

前端浏览器无法直连 mcp 容器的 Streamable HTTP（会触发 MCP 协议握手），
故由 backend 代理探测 mcp 的 /healthz（轻量 REST），汇总成状态返回。
本接口不暴露给 MCP 自身（契约表 /mcp/status 标 expose=false，避免循环依赖）。

用标准库 urllib 探测，避免给 backend 生产 venv 引入 httpx 依赖。
"""

import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter

from ..config import settings
from ..schemas.common import ApiResponse

router = APIRouter()


def _healthz_url(mcp_url: str) -> str:
    """从 mcp_url（如 http://mcp:8020/mcp）推出健康探测地址 http://mcp:8020/healthz。"""
    p = urlsplit(mcp_url.rstrip("/"))
    return urlunsplit((p.scheme, p.netloc, "/healthz", "", ""))


def _probe_healthz(url: str, timeout: float = 3.0) -> dict | None:
    """GET mcp /healthz，返回其 JSON；失败（连不通 / 非 200）返回 None。"""
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — 内部固定 URL
            if resp.status != 200:
                return None
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None


@router.get("/status", response_model=ApiResponse)
def mcp_status() -> ApiResponse:
    healthz = _healthz_url(settings.mcp_url)
    now = datetime.now(timezone.utc).isoformat()

    # mcp 离线时，本接口能响应即证明 backend 自身可达。
    enabled = False
    backend_reachable = True
    tool_count = 0
    tools: list = []
    last_check = now

    data = _probe_healthz(healthz)
    if data is not None:
        enabled = True
        backend_reachable = bool(data.get("backend_reachable"))
        tool_count = int(data.get("tool_count", 0))
        tools = data.get("tools", [])
        last_check = data.get("last_check", now)

    return ApiResponse.ok(
        data={
            "enabled": enabled,
            "mcp_url": settings.mcp_url_public,
            "backend_reachable": backend_reachable,
            "tool_count": tool_count,
            "tools": tools,
            "last_check": last_check,
        }
    )
