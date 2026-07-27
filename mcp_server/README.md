# PortLab MCP Server

把 PortLab 后端的 **32 个精挑接口**包装成 [MCP](https://modelcontextprotocol.io) tool，让 LLM（ZCode / Claude 等）能在对话里直接「查估值、跑回测、看市场、分析事件冲击」，无需人工点前端。

- **独立容器**：只依赖 `fastmcp + httpx`，**不 import backend**（不拉 fastapi/sqlalchemy/akshare/tushare）。
- **只读查询 + 回测创建**：隐藏改配置 / 删数据 / LLM-in-LLM 类接口，避免误操作。
- **chart 自动降采样**：回测曲线从 ~2500 点压到 ~80 点（保留首尾 + 买卖信号日），防 LLM 上下文爆炸。
- **契约表治理**：`docs/api-registry.yaml` 是「暴露什么」的单一事实源，启动时与实际注册 tool 交叉校验漂移。

## 快速启动

### 方式一：Docker Compose（推荐，与 backend/frontend 一起起）

```bash
docker compose up -d --build      # 起 mysql + backend + frontend + mcp
# 或只起 mcp：
docker compose up -d --build mcp
```

启动后 MCP 端点：`http://localhost:8020/mcp`（Streamable HTTP）。
健康检查（REST，不走 MCP 协议）：`curl http://localhost:8020/healthz`。

### 方式二：本地裸跑（调试用）

```bash
cd mcp_server
uv sync
PORTLAB_API_BASE=http://localhost:8010/api \
MCP_REGISTRY_PATH=../docs/api-registry.yaml \
uv run python -m portlab_mcp.server
```

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `PORTLAB_API_BASE` | `http://localhost:8010/api` | backend 基址；容器间为 `http://backend:8010/api` |
| `MCP_HOST` | `0.0.0.0` | 监听地址（容器内需 0.0.0.0） |
| `MCP_HTTP_PORT` | `8020` | 监听端口 |
| `MCP_REGISTRY_PATH` | `/app/api-registry.yaml` | 契约表路径（compose 以只读卷挂载） |
| `MCP_CHART_TARGET_POINTS` | `80` | chart 降采样目标点数 |

## 客户端配置

### ZCode / Claude Desktop / 任意 Streamable HTTP 客户端

```json
{
  "mcpServers": {
    "portlab": {
      "url": "http://localhost:8020/mcp"
    }
  }
}
```

> 远程访问时把 `localhost` 换成宿主机 IP。前端导航栏右上角的 **MCP 图标 → 复制 ZCode 配置** 可一键拿到这段 JSON。

## 暴露的 32 个 tool

按分组（与状态面板分组一致）：

**系统 / 元信息（5）**
`health_check` · `get_roadmap` · `get_release_notes` · `get_recent_backtests` · `search_symbols`

**市场 / 估值（5）**
`get_market_overview` · `get_etf_flow` · `get_valuation_indices` · `get_valuation_single` · `get_valuation_overlay`（降采样）

**回测创建（5）**
`run_dca_backtest` · `run_ma120_backtest` · `run_grid_backtest` · `run_portfolio_backtest` · `save_drawboard_backtest`

**回测结果查询（10，chart 走降采样）**
`get_dca_chart` / `get_dca_summary` · `get_ma120_chart` / `get_ma120_summary` · `get_grid_chart` / `get_grid_summary` · `get_portfolio_chart` / `get_portfolio_summary` · `get_drawboard_chart` / `get_drawboard_summary`

**回撤看板交互（2）**
`get_drawboard_series`（降采样） · `run_drawboard_realtime`（降采样）

**事件冲击（4）**
`get_event_themes` · `get_event_theme_detail` · `get_event_detail` · `get_event_impact`（window_returns 降采样）

**策略擂台（1）**
`compare_strategies`（归一化净值降采样）

> 隐藏的 19 个接口（数据拉取 / 数据源配置 / 各 preview / event 配置与智能匹配 / feedback / 旧 valuation）及逐条理由见 `docs/api-registry.yaml` 的 `mcp.hide_reason`。

## 典型用法

**示例 1：查估值**
> 「沪深300 现在贵不贵？」
> 调 `get_valuation_single(symbol="000300", lookback="5y")` → 返回 PE 通道 + 历史分位 →「当前 PE 12.3，5 年分位 35%，偏低估区」。

**示例 2：跑回测**
> 「510880 过去 3 年 MA120 策略表现如何？」
> `run_ma120_backtest(symbol="510880", start_date="2023-01-01", end_date="2026-07-27", capital_mode="fixed", principal=100000)` → 拿 `task_id` → `get_ma120_summary(task_id)` →「年化 8.8%，最大回撤 8.8%，胜率 100%」→ 必要时 `get_ma120_chart(task_id)` 看曲线（已降采样）。

**示例 3：对比策略**
> 「510880 上定投和 MA120 哪个好？」
> `compare_strategies(mode="cross_strategy", symbol="510880")` → 归一化净值对比 + 指标表。

## 契约表维护流程

`docs/api-registry.yaml` 是 MCP tool 与 backend 接口对齐的单一事实源（解决「backend 加了接口 MCP 不知道」的漂移）。

1. **backend 新增 / 修改接口**：在 `docs/api-registry.yaml` 加 / 改一条记录，填 `mcp.expose`（true/false）、`tool_name`、`group`、`sample`。
2. **暴露新 tool**：在 `src/portlab_mcp/tools/<domain>.py` 手写对应 tool 函数（入参与 backend Pydantic schema 对齐，见各 tool 的签名 + docstring）。
3. **重启 mcp 容器**：`docker compose restart mcp`（契约表只读挂载，改 YAML 无需重 build）。
4. **漂移自检**：`/healthz` 的 `drift_warnings` 字段会报告「契约表声明但未注册 / 注册了但契约表没有」的差异；前端状态面板也能看到。

## 架构

```
LLM ──(MCP Streamable HTTP)──► mcp_server :8020/mcp
                                   │  (client.call 解包 ApiResponse 信封)
                                   ▼
                              backend :8010/api ──► MySQL / 数据源
```

- `client.py`：单例 httpx，统一解包 `{code,message,data}`；`code≠0` 抛中文 message 给 LLM。
- `transforms.py`：chart 降采样（linspace + 信号日预留名额 + 嵌套小对象保留）。
- `registry_loader.py`：解析契约表 → ToolSpec，供 `/healthz` 分组与漂移检查。
- `tools/*.py`：6 个领域模块，手写 tool 签名（给 LLM 清晰入参）。
- `server.py`：FastMCP 实例 + `/healthz` 自定义路由 + HTTP 传输入口。

> **测试**：`uv run pytest`（`tests/test_transforms.py` 降采样逻辑 + `tests/test_registry.py` 契约表解析）。
