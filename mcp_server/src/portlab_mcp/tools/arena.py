"""策略擂台 tool：横向对比（同标的多策略 / 同策略多标的），归一化净值已降采样。"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import PortLabClient
from ._util import _clean, _sampled


def register(mcp: FastMCP, client: PortLabClient) -> None:
    @mcp.tool(tags={"arena"})
    async def compare_strategies(
        mode: str,
        symbol: str | None = None,
        strategy: str | None = None,
        symbols: list[str] | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> dict:
        """横向对比策略，返回归一化净值叠加 + 指标表（净值曲线已降采样到 ~80 点）。

        mode: cross_strategy（同标的多策略对比，需 symbol）
              / cross_symbol（同策略多标的对比，需 strategy）。
        symbol: cross_strategy 模式必填，6 位代码。
        strategy: cross_symbol 模式必填，dca/ma120/grid/drawboard 之一。
        symbols: cross_symbol 模式下的标的代码列表。
        start / end: 可选 YYYY-MM-DD，限定对比区间。
        """
        return await _sampled(
            client,
            "/arena/compare",
            "chart80",
            _clean(
                {
                    "mode": mode,
                    "symbol": symbol,
                    "strategy": strategy,
                    "symbols": symbols,
                    "start": start,
                    "end": end,
                }
            ),
        )
