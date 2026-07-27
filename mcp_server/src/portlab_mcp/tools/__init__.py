"""Tool 注册入口。

每个领域模块导出 ``register_<domain>(mcp, client)``，``register_all`` 依次调用。
契约表漂移校验在 /healthz（async，见 server.py）里做——那里才能 await list_tools。
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import PortLabClient
from ..registry_loader import ToolSpec


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    """去掉值为 None 的键（让 backend 用自身默认值）。"""
    return {k: v for k, v in d.items() if v is not None}


def register_all(mcp: FastMCP, client: PortLabClient, specs: list[ToolSpec]) -> None:
    """注册全部领域 tool（各模块手写签名 + docstring，给 LLM 清晰入参）。"""
    # 延迟 import 避免循环依赖。
    from . import arena, backtest, drawboard, event, market, system

    system.register(mcp, client)
    market.register(mcp, client)
    backtest.register(mcp, client)
    drawboard.register(mcp, client)
    event.register(mcp, client)
    arena.register(mcp, client)


__all__ = ["register_all", "_clean"]
