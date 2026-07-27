"""PortLab MCP Server 入口。

- FastMCP 实例 + Streamable HTTP 传输（默认路径 /mcp）。
- /healthz 自定义路由：供 backend /api/mcp/status 探测，返回 tool 清单（带分组）+
  backend 连通性，不走 MCP 协议。
- 启动顺序：建 client → 读契约表 → 注册 tool → run。
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

from .client import PortLabClient
from .config import settings
from .registry_loader import check_drift, group_map, load_registry
from .tools import register_all

INSTRUCTIONS = (
    "PortLab 是 A 股投资分析工具箱。可用能力：查指数估值（PE 通道 / 分位 / 多指数叠加）、"
    "跑回测（定投 / MA120 红利 / 网格 / 组合 / 回撤买入）、看市场概览与 ETF 资金流、"
    "分析事件冲击产业链、横向对比策略。\n"
    "回测标准流程：先 run_*_backtest（或 save_drawboard_backtest）拿 task_id，"
    "再 get_*_summary 看核心指标（年化 / 回撤 / 胜率），需要看曲线时调 get_*_chart（已降采样）。\n"
    "标的代码统一 6 位（如 510880 红利 ETF、000300 沪深300）；日期格式 YYYY-MM-DD。\n"
    "所有返回经 ApiResponse 信封解包；业务错误会以中文 message 抛出，据此修正参数重试。"
)

mcp = FastMCP("PortLab", instructions=INSTRUCTIONS)

# 运行期单例（build() 注入）。
_client: PortLabClient | None = None
_groups: dict[str, str] = {}


def _resolve_registry_path() -> str:
    p = Path(settings.mcp_registry_path)
    if p.exists():
        return str(p)
    # 本地裸跑：契约表可能在仓库根 docs/ 下（相对 mcp_server/ 的上一级）。
    for cand in (Path("../docs/api-registry.yaml"), Path("docs/api-registry.yaml")):
        if cand.exists():
            return str(cand.resolve())
    return str(p)  # 不存在也返回，load 时报错更明确


def build() -> None:
    """构造 client + 读契约表 + 注册 tool。"""
    global _client, _groups
    _client = PortLabClient(settings.portlab_api_base)
    reg_path = _resolve_registry_path()
    specs = load_registry(reg_path)
    _groups = group_map(specs)
    register_all(mcp, _client, specs)
    print(f"[mcp] 已注册 tool（契约表 expose=true 共 {len(specs)} 条）", file=sys.stderr)


@mcp.custom_route("/healthz", methods=["GET"])
async def healthz(request: Request) -> JSONResponse:
    """轻量健康检查（不走 MCP 协议）。

    供 backend /api/mcp/status 探测：返回 tool 清单（含分组）+ mcp→backend 连通性。
    """
    # 列出实际注册的 tool，按契约表 group 标分组。
    tools_raw = await mcp.list_tools()
    tools = [
        {"name": t.name, "group": _groups.get(t.name, "misc"), "desc": t.description or ""}
        for t in tools_raw
    ]

    # mcp → backend 连通性探测（短超时，/health 无 DB 很快）。
    backend_reachable = False
    base = settings.portlab_api_base.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=3.0) as probe:
            r = await probe.get(f"{base}/health")
            backend_reachable = r.status_code == 200
    except Exception:  # noqa: BLE001 — 探测失败即不可达
        backend_reachable = False

    # 漂移告警（诊断用，附在响应里）：契约表声明 vs 实际注册。
    specs = load_registry(_resolve_registry_path())
    warns = check_drift(specs, {t["name"] for t in tools})

    return JSONResponse(
        {
            "status": "ok",
            "tool_count": len(tools),
            "tools": tools,
            "backend_reachable": backend_reachable,
            "drift_warnings": warns,
            "last_check": datetime.now(UTC).isoformat(),
        }
    )


def main() -> None:
    build()
    # path=/mcp 为 Streamable HTTP 默认端点；ZCode/Claude 等客户端连 http://host:port/mcp
    mcp.run(transport="http", host=settings.mcp_host, port=settings.mcp_http_port, path="/mcp")


if __name__ == "__main__":
    main()
