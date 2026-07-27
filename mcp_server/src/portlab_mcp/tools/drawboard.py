"""回撤买入 drawboard tool：底图序列 + 实时回测 + 落库 + 图表/汇总查询。"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import PortLabClient
from ._util import _clean, _get, _post, _sampled


def register(mcp: FastMCP, client: PortLabClient) -> None:
    @mcp.tool(tags={"drawboard"})
    async def get_drawboard_series(
        symbol: str,
        start: str | None = None,
        end: str | None = None,
    ) -> dict:
        """取回撤买入看板底图：价格 + 滚动最大回撤 + 基准累计涨幅
        （已降采样，标的组与基准组各自切片）。

        symbol: 6 位代码。start/end: 可选 YYYY-MM-DD。
        """
        return await _sampled(
            client, "/drawboard/series", "chart80", {"symbol": symbol, "start": start, "end": end}
        )

    @mcp.tool(tags={"drawboard"})
    async def run_drawboard_realtime(
        symbol: str,
        start_date: str,
        end_date: str,
        threshold: float = 20.0,
        step: float = 5.0,
        buy_amount: float = 10000.0,
        add_amount: float = 5000.0,
        sell_mode: str = "new_high",
        reinvest: bool = False,
    ) -> dict:
        """实时重算回撤买入回测（不落库，含图表 + 汇总，图表已降采样）。

        策略：回撤达 threshold% 首买，每再多跌 step% 加仓；按 sell_mode 兑现。
        symbol: 6 位代码。start_date/end_date: YYYY-MM-DD。
        threshold: 回撤买入阈值 %（默认 20）。step: 每再多跌 N% 加仓（默认 5）。
        buy_amount: 首次买入金额（默认 10000）。add_amount: 每次加仓金额（默认 5000）。
        sell_mode: none（不卖）/ new_high（创新高清仓，默认）/ partial（部分止盈）。
        reinvest: 复利——按净资产高水位放大买入（默认 False）。
        """
        data = await client.call(
            "GET",
            "/drawboard/backtest",
            params=_clean(
                {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "threshold": threshold,
                    "step": step,
                    "buy_amount": buy_amount,
                    "add_amount": add_amount,
                    "sell_mode": sell_mode,
                    "reinvest": reinvest,
                }
            ),
        )
        # 实时回测 = 图表 + summary；仅对图表部分降采样。
        if isinstance(data, dict):
            from ..config import settings
            from ..transforms import downsample_chart

            chart = {k: v for k, v in data.items() if k != "summary"}
            summary = data.get("summary")
            out = downsample_chart(chart, settings.mcp_chart_target_points)
            if summary is not None:
                out["summary"] = summary
            return out
        return data

    @mcp.tool(tags={"drawboard"})
    async def save_drawboard_backtest(
        symbol: str,
        start_date: str,
        end_date: str,
        threshold: float = 20.0,
        step: float = 5.0,
        buy_amount: float = 10000.0,
        add_amount: float = 5000.0,
        sell_mode: str = "new_high",
        reinvest: bool = False,
    ) -> dict:
        """保存回撤回测到库（返回 {task_id}，幂等）。参数同 run_drawboard_realtime。"""
        return await _post(
            client,
            "/drawboard/save",
            _clean(
                {
                    "symbol": symbol,
                    "start_date": start_date,
                    "end_date": end_date,
                    "threshold": threshold,
                    "step": step,
                    "buy_amount": buy_amount,
                    "add_amount": add_amount,
                    "sell_mode": sell_mode,
                    "reinvest": reinvest,
                }
            ),
        )

    @mcp.tool(tags={"drawboard"})
    async def get_drawboard_chart(task_id: str) -> dict:
        """取落库回撤回测图表（已降采样）。"""
        return await _sampled(client, f"/drawboard/{task_id}/chart", "chart80")

    @mcp.tool(tags={"drawboard"})
    async def get_drawboard_summary(task_id: str) -> dict:
        """取落库回撤回测汇总：投入 / 收益 / 年化 / 回撤 / 买卖次数 / sell_mode。"""
        return await _get(client, f"/drawboard/{task_id}/summary")
