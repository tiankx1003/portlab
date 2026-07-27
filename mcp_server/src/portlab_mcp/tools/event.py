"""事件冲击产业链 tool（只读子集）：主题模板 / 主题详情 / 事件详情 / 事件冲击三视图。"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import PortLabClient
from ._util import _get, _sampled


def register(mcp: FastMCP, client: PortLabClient) -> None:
    @mcp.tool(tags={"event"})
    async def get_event_themes() -> list:
        """返回全部事件主题模板（如「国产替代」「新能源」），含成分股数量。用于选主题建事件。"""
        return await _get(client, "/event/themes")

    @mcp.tool(tags={"event"})
    async def get_event_theme_detail(theme_id: int) -> dict:
        """取主题详情（含成分股清单）。

        theme_id: 主题 ID（先 get_event_themes 拿到）。
        """
        return await _get(client, f"/event/themes/{theme_id}")

    @mcp.tool(tags={"event"})
    async def get_event_detail(event_id: int) -> dict:
        """取事件详情（事件名 / 日期 / 标的池）。event_id: 事件 ID。"""
        return await _get(client, f"/event/{event_id}")

    @mcp.tool(tags={"event"})
    async def get_event_impact(event_id: int, before: int = 20, after: int = 20) -> dict:
        """取事件冲击三视图：归一化收益曲线 + 涨跌排行 + 相关性热力图。

        event_id: 事件 ID。before/after: 事件前/后窗口（0-120 交易日，默认各 20）。
        返回的 window_returns / benchmark_series 已降采样到 ~80 点；
        correlation_matrix / ranking 等小对象保留原样。
        """
        return await _sampled(
            client,
            f"/event/{event_id}/impact",
            "event_impact",
            {"event_id": event_id, "before": before, "after": after},
        )
