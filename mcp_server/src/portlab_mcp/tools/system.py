"""系统 / 元信息 tool：健康检查、roadmap、更新日志、最近回测、标的搜索。"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import PortLabClient
from ._util import _get


def register(mcp: FastMCP, client: PortLabClient) -> None:
    @mcp.tool(tags={"system"})
    async def health_check() -> dict:
        """检查 PortLab 后端是否在线。无副作用，可随时调用。返回 {status: ok}。"""
        return await client.call("GET", "/health")

    @mcp.tool(tags={"system"})
    async def get_roadmap() -> list:
        """返回 PortLab 尚未实现的任务清单（来自 TASKS.md 的 ☐ 项），每条含编号/标题/摘要。"""
        return await _get(client, "/roadmap")

    @mcp.tool(tags={"system"})
    async def get_release_notes() -> list:
        """返回最近 5 条 PortLab 更新日志（功能/修复/优化），了解最新能力。"""
        return await _get(client, "/release-notes")

    @mcp.tool(tags={"system"})
    async def get_recent_backtests(limit: int = 5) -> list:
        """返回最近手动保存的回测记录（合并定投/MA120/网格/组合/回撤各策略）。

        limit: 返回条数 1-20，默认 5。用于找到之前跑过的 task_id 再查详情/图表。
        """
        return await _get(client, "/backtest/recent", {"limit": limit})

    @mcp.tool(tags={"system"})
    async def search_symbols(q: str) -> list:
        """A 股代码 / 名称模糊搜索（如 "红利"、"510880"），返回 top 30 候选。

        q: 搜索关键词（代码或名称片段），必填。用于把用户口语标的名解析成 6 位代码。
        """
        return await _get(client, "/symbols/search", {"q": q})
