"""回测 tool：DCA 定投 / MA120 红利 / 网格 / 组合 的创建 + 图表(降采样) + 汇总。

创建类（POST）返回 {task_id}；拿到 task_id 后用 get_*_summary 看指标、get_*_chart 看曲线。
入参与 backend Pydantic schema 对齐（app.schemas.{backtest,ma120,grid,portfolio}），
不 import backend。
"""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from ..client import PortLabClient
from ._util import _clean, _get, _post, _sampled


def _body(**kw: Any) -> dict[str, Any]:
    """从命名参数构造请求体，丢 None（让 backend 用默认值）。"""
    return _clean(kw)


def register(mcp: FastMCP, client: PortLabClient) -> None:
    # ========== DCA 定投 ==========
    @mcp.tool(tags={"backtest"})
    async def run_dca_backtest(
        symbol: str,
        frequency: str,
        amount: float,
        start_date: str,
        end_date: str,
        invest_day: int,
        mode: str = "normal",
        ma_period: int = 250,
    ) -> dict:
        """创建定投回测（普通 / 智能均线），返回 {task_id}。幂等：同参数命中即返回已有 task_id。

        symbol: 6 位代码如 510880。
        frequency: weekly（按周）/ monthly（按月）。
        amount: 每期定投金额（>0）。
        start_date / end_date: YYYY-MM-DD，start 必须早于 end。
        invest_day: weekly 取 0-6（周一~周日）；monthly 取 1-28。
        mode: normal（普通定投）/ smart（按均线偏离度动态扣款，默认 normal）。
        ma_period: smart 模式均线周期，默认 250（ge=2 le=1000）。
        """
        return await _post(
            client,
            "/backtest/dca",
            _body(
                symbol=symbol,
                frequency=frequency,
                amount=amount,
                start_date=start_date,
                end_date=end_date,
                invest_day=invest_day,
                mode=mode,
                ma_period=ma_period,
            ),
        )

    @mcp.tool(tags={"backtest"})
    async def get_dca_chart(task_id: str) -> dict:
        """取定投回测逐日图表（已降采样到 ~80 点，保留买卖信号日）。"""
        return await _sampled(client, f"/backtest/dca/{task_id}/chart", "chart80")

    @mcp.tool(tags={"backtest"})
    async def get_dca_summary(task_id: str) -> dict:
        """取定投回测汇总：投入 / 收益 / XIRR 年化 / 最大回撤 / 胜率 / 买卖次数。"""
        return await _get(client, f"/backtest/dca/{task_id}/summary")

    # ========== MA120 红利策略 ==========
    @mcp.tool(tags={"backtest"})
    async def run_ma120_backtest(
        symbol: str,
        start_date: str,
        end_date: str,
        capital_mode: str,
        principal: float | None = None,
        monthly_amount: float | None = None,
        splits: int = 10,
        ma_period: int = 120,
        buy_threshold: float = 0.985,
        step: float = 0.01,
        crash_threshold: float = 0.05,
        crash_multiplier: int = 2,
        sell_mode: str = "batch",
        batch_sell_step: float = 0.02,
        dividend_mode: str = "cash",
    ) -> dict:
        """创建 MA120 红利策略回测，返回 {task_id}。

        策略：价格跌破 MA120 × 阈值金字塔分批买入，站回 MA 上方分批/全部/半仓兑现。
        symbol: 6 位代码。start_date/end_date: YYYY-MM-DD。
        capital_mode: fixed（固定本金）/ recurring（每月投入）/ hybrid（混合）。
          fixed 需 principal>0；recurring 需 monthly_amount>0；hybrid 两者皆需。
        principal: 初始本金（fixed/hybrid 必填）。
        monthly_amount: 月度投入（recurring/hybrid 必填）。
        splits: 初始本金份数（默认 10）。ma_period: 均线周期（默认 120）。
        buy_threshold: 起始买入阈值（默认 0.985，即跌破 MA 的 98.5%）。
        step: 加仓步长（默认 0.01）。crash_threshold: 暴跌阈值（默认 0.05）。
        crash_multiplier: 暴跌加倍倍数（默认 2）。
        sell_mode: batch（分批止盈，默认）/ all（全部兑现）/ half（半仓）。
        batch_sell_step: 止盈步长（默认 0.02）。
        dividend_mode: cash（现金，默认）/ reinvest（复利再投）。
        """
        return await _post(
            client,
            "/backtest/ma120",
            _body(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                capital_mode=capital_mode,
                principal=principal,
                monthly_amount=monthly_amount,
                splits=splits,
                ma_period=ma_period,
                buy_threshold=buy_threshold,
                step=step,
                crash_threshold=crash_threshold,
                crash_multiplier=crash_multiplier,
                sell_mode=sell_mode,
                batch_sell_step=batch_sell_step,
                dividend_mode=dividend_mode,
            ),
        )

    @mcp.tool(tags={"backtest"})
    async def get_ma120_chart(task_id: str) -> dict:
        """取 MA120 回测逐日图表（已降采样到 ~80 点，保留买卖信号日 + MA 线）。"""
        return await _sampled(client, f"/backtest/ma120/{task_id}/chart", "chart80")

    @mcp.tool(tags={"backtest"})
    async def get_ma120_summary(task_id: str) -> dict:
        """取 MA120 回测汇总：投入 / 收益 / 年化 / 最大回撤 / 胜率 / 买卖次数。"""
        return await _get(client, f"/backtest/ma120/{task_id}/summary")

    # ========== 网格交易 ==========
    @mcp.tool(tags={"backtest"})
    async def run_grid_backtest(
        symbol: str,
        start_date: str,
        end_date: str,
        center_price: float,
        step_pct: float = 3.0,
        amount_per_level: float = 5000.0,
        n_levels_above: int = 5,
        n_levels_below: int = 5,
        bound_mode: str = "hold",
    ) -> dict:
        """创建网格交易回测，返回 {task_id}。

        策略：中枢 + 间距双向触发——每跌一档买入、每涨一档卖出，吃震荡。
        symbol: 6 位代码。start_date/end_date: YYYY-MM-DD。
        center_price: 网格中枢价（元，>0）。step_pct: 网格间距 %（默认 3）。
        amount_per_level: 每格资金（默认 5000）。n_levels_above/below: 上下方格数（默认各 5）。
        bound_mode: 价格越界处理 hold（持有，默认）/ stop（平仓）/ reset（重置中枢）。
        """
        return await _post(
            client,
            "/backtest/grid",
            _body(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                center_price=center_price,
                step_pct=step_pct,
                amount_per_level=amount_per_level,
                n_levels_above=n_levels_above,
                n_levels_below=n_levels_below,
                bound_mode=bound_mode,
            ),
        )

    @mcp.tool(tags={"backtest"})
    async def get_grid_chart(task_id: str) -> dict:
        """取网格回测逐日图表（已降采样，保留 grid_levels 网格线与买卖信号日）。"""
        return await _sampled(client, f"/backtest/grid/{task_id}/chart", "chart80")

    @mcp.tool(tags={"backtest"})
    async def get_grid_summary(task_id: str) -> dict:
        """取网格回测汇总：网格利润 / 循环次数 / 年化 / 最大回撤。"""
        return await _get(client, f"/backtest/grid/{task_id}/summary")

    # ========== 组合回测 ==========
    @mcp.tool(tags={"backtest"})
    async def run_portfolio_backtest(
        symbols: list[str],
        start_date: str,
        end_date: str,
        mode: str = "fixed",
        weights: list[float] | None = None,
        rebalance: str = "monthly",
        rf: float = 0.025,
        allow_short: bool = False,
    ) -> dict:
        """创建组合回测，返回 {task_id}。可求有效前沿最优权重（最小方差 / 最大夏普）。

        symbols: 标的代码列表（2-12 个，去重）。start_date/end_date: YYYY-MM-DD。
        mode: fixed（指定权重）/ frontier（求有效前沿最优权重，默认 fixed）。
        weights: fixed 模式必填，长度须等于 symbols。
        rebalance: 调仓频率 monthly（默认）/ quarterly / none。
        rf: 无风险利率（小数，默认 0.025）。allow_short: 是否允许做空（默认 False）。
        """
        return await _post(
            client,
            "/backtest/portfolio",
            _body(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                mode=mode,
                weights=weights,
                rebalance=rebalance,
                rf=rf,
                allow_short=allow_short,
            ),
        )

    @mcp.tool(tags={"backtest"})
    async def get_portfolio_chart(task_id: str) -> dict:
        """取组合回测图表（已降采样；相关性矩阵 / 有效前沿点等小对象不降采样）。"""
        return await _sampled(client, f"/backtest/portfolio/{task_id}/chart", "chart80")

    @mcp.tool(tags={"backtest"})
    async def get_portfolio_summary(task_id: str) -> dict:
        """取组合回测汇总：年化 / 波动 / 夏普 / 最大回撤 / 权重。"""
        return await _get(client, f"/backtest/portfolio/{task_id}/summary")
