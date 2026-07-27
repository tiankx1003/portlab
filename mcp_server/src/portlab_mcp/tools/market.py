"""市场 / 估值 tool：市场概览、ETF 资金流、估值看板（指数列表 / 单指数通道 / 多指数叠加）。"""

from __future__ import annotations

from fastmcp import FastMCP

from ..client import PortLabClient
from ._util import _get, _sampled


def register(mcp: FastMCP, client: PortLabClient) -> None:
    @mcp.tool(tags={"market"})
    async def get_market_overview(extra: str | None = None) -> dict:
        """市场概览：预置指数（沪深300 / 红利ETF / 红利低波）最新价、涨跌幅、迷你 sparkline。

        extra: 可选，追加一个自定义指数代码到概览。了解当前市场温度用。
        """
        return await _get(client, "/market/overview", {"extra": extra})

    @mcp.tool(tags={"market"})
    async def get_etf_flow(
        symbol: str = "510880", start: str | None = None, end: str | None = None
    ) -> dict:
        """ETF 三路资金信号：份额变动、北向资金、主力资金（Tushare 源，观察机构/国家队动向）。

        symbol: ETF 代码，默认 510880（红利 ETF）。
        start / end: 可选日期 YYYY-MM-DD，限定区间。
        """
        return await _get(client, "/etf-flow", {"symbol": symbol, "start": start, "end": end})

    @mcp.tool(tags={"market"})
    async def get_valuation_indices() -> dict:
        """返回估值看板支持的指数清单（12 条登记，含 supported 灰显与无数据说明）。

        用于先看哪些指数有 PE 数据，再调 get_valuation_single。
        """
        return await _get(client, "/valuation/indices")

    @mcp.tool(tags={"market"})
    async def get_valuation_single(
        symbol: str,
        lookback: str = "5y",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """单指数估值：PE 通道（5 条线分高估/中性/低估带）+ 历史分位 + 当前 PE/PB/股息率。

        symbol: 指数代码，如 000300（沪深300）、000922（中证红利）、000905（中证500）。
        lookback: 回看窗口 1y/3y/5y/7y/10y/all，默认 5y。
        start_date / end_date: 可选自定义区间（YYYY-MM-DD），覆盖 lookback。
        典型用法：问「沪深300 现在贵不贵」→ 看返回的 percentile 与 channel_position。
        """
        return await _get(
            client,
            "/valuation/single",
            {
                "symbol": symbol,
                "lookback": lookback,
                "start_date": start_date,
                "end_date": end_date,
            },
        )

    @mcp.tool(tags={"market"})
    async def get_valuation_overlay(
        symbols: str,
        base: int = 1,
        lookback: str = "5y",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """多指数 PE 归一化叠加曲线（已降采样到 ~80 点，各 series 同步切片），横向比估值高低。

        symbols: 逗号分隔多指数代码，如 "000300,000922,000905"。
        base: 归一化基准 1 或 1000，默认 1（起点=1）。
        lookback: 回看窗口，默认 5y。
        """
        return await _sampled(
            client,
            "/valuation/overlay",
            "chart80",
            {
                "symbols": symbols,
                "base": base,
                "lookback": lookback,
                "start_date": start_date,
                "end_date": end_date,
            },
        )
