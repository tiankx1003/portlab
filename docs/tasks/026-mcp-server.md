# 026 — PortLab MCP Server：把现有 API 暴露给 LLM

## 目标

把 PortLab 后端现有的 51 个 HTTP API 中**精挑过的子集**包装成 [MCP](https://modelcontextprotocol.io) tool，让 LLM（ZCode/Claude 等）能直接调用「查估值、跑回测、看市场、分析事件冲击」，无需人类手动点前端。

**为什么做**：
- 当前用 PortLab 的姿势是「打开浏览器 → 填表单 → 看图表」。MCP 化后，LLM 能在对话里直接说「帮我看看沪深300 现在估值贵不贵，顺便跑一下 510880 过去 3 年的 MA120 回测」并自主完成。
- 回测/估值/事件分析本质是「参数进、结构化结果出」的函数调用，正是 MCP tool 的理想场景。

**为什么是现在**：
- 后端 51 个接口已稳定（无认证、CORS 全开、ApiResponse 信封统一、schema 齐备）。
- Pydantic schema 带 `Field(description/pattern/gt/ge)`，可直接喂给 FastMCP 当 tool 入参。
- `httpx` 已在依赖中。

---

## 核心设计决策（已与用户确认）

| 决策点 | 选定方案 | 理由 |
|--------|----------|------|
| 部署形态 | 独立目录 `mcp_server/` + 独立 pyproject + **独立容器** | 与 backend 解耦，依赖最小化（只 fastmcp+httpx） |
| 传输方式 | **HTTP（Streamable HTTP）** | 适合容器化 + 远程共享；ZCode 配 URL 连 |
| 暴露范围 | **只读查询 + 回测创建** | 隐藏改配置/删数据/LLM-in-LLM 类，避免误操作 |
| chart 数据策略 | **降采样到 ~80 点** | 单次 chart ~70K tokens 会爆 LLM 上下文，必须截断 |
| 接口契约治理 | **`docs/api-registry.yaml` 单一事实源**（方案 2） | 新增接口时人工更新此表，机械决定是否暴露；演进到方案 3（路由装饰器自动生成）列为开放问题 |

---

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)（docker compose 框架）
- 现有全部已交付任务的后端接口（007 MA120 / 015-019 drawboard / 016 估值 / 020 网格 / 022 组合 / 023 擂台 / 018 事件 等）

> MCP 是「消费层」，不改 backend 任何代码、不依赖未交付的任务。024（估值 v2）若交付则其新端点也按本任务的契约表机制纳入（Part 0 已预填其三条端点）。

---

## Part 0：接口契约表（`docs/api-registry.yaml`）—— 治理基础设施

**这是本任务最关键的产物**，解决「新增接口如何及时集成进 MCP」的治理问题。本任务交付物不含此文件，仅在此文档定义其完整内容；026 实施时落地为独立文件 `docs/api-registry.yaml`。

### 为什么需要

MCP tool 与 backend 接口天然是**两份**，会漂移：backend 加了 `/api/foo`，MCP 侧不知道；MCP 暴露了 `/api/bar`，后来 backend 改了参数 schema，MCP 还在用旧定义。需要一个**单一事实源**让两边对齐。

### 文件位置与形态

`docs/api-registry.yaml`（与 TASKS.md 平级），人工维护，YAML 格式。每个 backend 接口一条记录：

```yaml
# PortLab API Registry — 接口契约单一事实源
# 维护规则：backend 新增/修改接口时，同步更新本文件；MCP server 启动时读本文件生成 tool 清单。
# 字段说明：
#   path/method:          backend 路由（不含 /api 前缀）
#   desc:                 一句话功能（MCP tool description 用）
#   mcp.expose:           是否暴露给 LLM（true/false）
#   mcp.tool_name:        暴露时的 tool 名（snake_case，expose=false 时留空）
#   mcp.sample:           降采样策略（none/chart80/summary_only/event_impact）
#   mcp.hide_reason:      expose=false 时的隐藏原因
#   params:               简单参数内联定义（type/required/default/desc）
#   params_ref:           复杂参数引用 backend Pydantic schema（如 app.schemas.ma120.Ma120Request）
#   notes:                特殊注意事项（慢/副作用/LLM-in-LLM 等）

version: 1
generated_at: "2026-07-27"

endpoints:
  # ===== 系统 / 元信息 =====
  - path: /health
    method: GET
    desc: 健康检查
    mcp: {expose: true, tool_name: health_check, sample: none}

  - path: /roadmap
    method: GET
    desc: 未完成任务列表（TASKS.md 中 ☐ 项）
    mcp: {expose: true, tool_name: get_roadmap, sample: none}

  - path: /release-notes
    method: GET
    desc: 最新 5 条更新日志
    mcp: {expose: true, tool_name: get_release_notes, sample: none}

  - path: /backtest/recent
    method: GET
    desc: 最近手动保存的回测记录
    mcp: {expose: true, tool_name: get_recent_backtests, sample: none}
    params: {limit: {type: int, default: 5, desc: "返回条数 1-20"}}

  - path: /symbols/search
    method: GET
    desc: A 股代码/名称模糊搜索
    mcp: {expose: true, tool_name: search_symbols, sample: none}
    params: {q: {type: str, required: true, desc: "搜索关键词"}}

  # ===== 数据与配置（全部隐藏）=====
  - path: /data/fetch
    method: POST
    desc: 触发行情拉取（慢，易触发限频）
    mcp: {expose: false, hide_reason: "拉数慢，LLM 高频试探会触发 akshare/tushare 限频"}

  - path: /datasource/status
    method: GET
    desc: 数据源状态
    mcp: {expose: false, hide_reason: "配置类，与 LLM 分析任务无关"}

  - path: /datasource/token
    method: PUT
    desc: 设置 Tushare Token
    mcp: {expose: false, hide_reason: "敏感配置写入，禁止 LLM 调用"}

  - path: /datasource/token
    method: DELETE
    desc: 清空 Token
    mcp: {expose: false, hide_reason: "敏感配置删除，禁止 LLM 调用"}

  - path: /datasource/toggle
    method: PUT
    desc: 开关 Tushare
    mcp: {expose: false, hide_reason: "配置切换，禁止 LLM 调用"}

  # ===== DCA 定投回测 =====
  - path: /backtest/dca
    method: POST
    desc: 创建定投回测（幂等命中即返回 task_id）
    mcp: {expose: true, tool_name: run_dca_backtest, sample: none}
    params_ref: app.schemas.backtest.BacktestRequest
    notes: "已修复（commit 2859567，2026-07-27）。DCA 创建链路可用。"

  - path: /backtest/dca/preview
    method: POST
    desc: 实时预览定投回测
    mcp: {expose: false, hide_reason: "与创建重复，preview 不落库对 LLM 用途有限；且 preview 控制流正常，可作为 run_dca 的实现参考"}

  - path: /backtest/dca/{task_id}/chart
    method: GET
    desc: 定投回测逐日图表（降采样到 ~80 点）
    mcp: {expose: true, tool_name: get_dca_chart, sample: chart80}
    params: {task_id: {type: str, required: true, desc: "回测任务 ID"}}

  - path: /backtest/dca/{task_id}/summary
    method: GET
    desc: 定投回测汇总指标
    mcp: {expose: true, tool_name: get_dca_summary, sample: none}
    params: {task_id: {type: str, required: true, desc: "回测任务 ID"}}

  # ===== MA120 回测 =====
  - path: /backtest/ma120
    method: POST
    desc: 创建 MA120 策略回测
    mcp: {expose: true, tool_name: run_ma120_backtest, sample: none}
    params_ref: app.schemas.ma120.Ma120Request
    notes: "已知 bug：create_ma120_backtest 控制流断，return 未缩进进 if 块。025 修复中。"

  - path: /backtest/ma120/preview
    method: POST
    desc: 实时预览 MA120 回测
    mcp: {expose: false, hide_reason: "与创建重复；preview 控制流正常，可作实现参考"}

  - path: /backtest/ma120/{task_id}/chart
    method: GET
    desc: MA120 回测逐日图表（降采样到 ~80 点）
    mcp: {expose: true, tool_name: get_ma120_chart, sample: chart80}
    params: {task_id: {type: str, required: true}}

  - path: /backtest/ma120/{task_id}/summary
    method: GET
    desc: MA120 回测汇总
    mcp: {expose: true, tool_name: get_ma120_summary, sample: none}
    params: {task_id: {type: str, required: true}}

  # ===== 网格交易回测 =====
  - path: /backtest/grid
    method: POST
    desc: 创建网格交易回测
    mcp: {expose: true, tool_name: run_grid_backtest, sample: none}
    params_ref: app.schemas.grid.GridRequest
    notes: "已知 bug：create_grid 控制流断，同 ma120。025 修复中。"

  - path: /backtest/grid/preview
    method: POST
    desc: 实时预览网格回测
    mcp: {expose: false, hide_reason: "与创建重复"}

  - path: /backtest/grid/{task_id}/chart
    method: GET
    desc: 网格回测逐日图表（降采样，保留 grid_levels）
    mcp: {expose: true, tool_name: get_grid_chart, sample: chart80}
    params: {task_id: {type: str, required: true}}

  - path: /backtest/grid/{task_id}/summary
    method: GET
    desc: 网格回测汇总（含网格利润、循环次数）
    mcp: {expose: true, tool_name: get_grid_summary, sample: none}
    params: {task_id: {type: str, required: true}}

  # ===== 组合回测 =====
  - path: /backtest/portfolio
    method: POST
    desc: 创建组合回测（fixed 指定权重 / frontier 求有效前沿）
    mcp: {expose: true, tool_name: run_portfolio_backtest, sample: none}
    params_ref: app.schemas.portfolio.PortfolioRequest
    notes: "✅ 已核查正常，return 本就在 if 块内。唯一观察：命中分支未调 log_save（不影响落库，仅 recent 列表不刷新）。"

  - path: /backtest/portfolio/{task_id}/chart
    method: GET
    desc: 组合回测图表（降采样，含相关性矩阵与前沿点，矩阵/前沿不降采样）
    mcp: {expose: true, tool_name: get_portfolio_chart, sample: chart80}
    params: {task_id: {type: str, required: true}}

  - path: /backtest/portfolio/{task_id}/summary
    method: GET
    desc: 组合回测汇总（年化/波动/夏普/回撤/权重）
    mcp: {expose: true, tool_name: get_portfolio_summary, sample: none}
    params: {task_id: {type: str, required: true}}

  # ===== 回撤买入 drawboard =====
  - path: /drawboard/series
    method: GET
    desc: 价格+回撤+基准底图
    mcp: {expose: true, tool_name: get_drawboard_series, sample: chart80}
    params: {symbol: {type: str, required: true}, start: {type: date}, end: {type: date}}

  - path: /drawboard/backtest
    method: GET
    desc: 实时重算回撤买入回测（不落库，含 sell_mode）
    mcp: {expose: true, tool_name: run_drawboard_realtime, sample: chart80}
    params_ref: app.schemas.drawboard.DrawboardRequest

  - path: /drawboard/save
    method: POST
    desc: 保存回撤回测到库（返回 task_id）
    mcp: {expose: true, tool_name: save_drawboard_backtest, sample: none}
    params_ref: app.schemas.drawboard.DrawboardRequest
    notes: "已知 bug：save 控制流断，同 ma120。025 修复中。"

  - path: /drawboard/{task_id}/chart
    method: GET
    desc: 落库回撤回测图表（降采样）
    mcp: {expose: true, tool_name: get_drawboard_chart, sample: chart80}
    params: {task_id: {type: str, required: true}}

  - path: /drawboard/{task_id}/summary
    method: GET
    desc: 落库回撤回测汇总
    mcp: {expose: true, tool_name: get_drawboard_summary, sample: none}
    params: {task_id: {type: str, required: true}}

  # ===== 估值看板 =====
  - path: /valuation/indices
    method: GET
    desc: 指数下拉项（含 supported 灰显）
    mcp: {expose: true, tool_name: get_valuation_indices, sample: none}
    notes: "024 交付后启用"

  - path: /valuation/single
    method: GET
    desc: 单指数 PE 通道 + 历史分位
    mcp: {expose: true, tool_name: get_valuation_single, sample: none}
    params: {symbol: {type: str, required: true, desc: "指数代码如 000300"}, lookback: {type: str, default: "5y", desc: "1y/3y/5y/7y/10y/all"}, start_date: {type: date}, end_date: {type: date}}
    notes: "024 交付后启用"

  - path: /valuation/overlay
    method: GET
    desc: 多指数叠加归一化
    mcp: {expose: true, tool_name: get_valuation_overlay, sample: chart80}
    params: {symbols: {type: str, required: true, desc: "逗号分隔多指数代码"}, base: {type: int, default: 1, desc: "归一化基准 1 或 1000"}, lookback: {type: str, default: "5y"}}
    notes: "024 交付后启用"

  - path: /valuation
    method: GET
    desc: 016 旧端点（向后兼容）
    mcp: {expose: false, hide_reason: "已被 /valuation/single 取代，保留仅为向后兼容；MCP 用新端点"}

  # ===== 市场 / 资金流 =====
  - path: /market/overview
    method: GET
    desc: 市场概览（预置指数最新价/涨跌/sparkline）
    mcp: {expose: true, tool_name: get_market_overview, sample: none}
    params: {extra: {type: str, desc: "可选自定义指数代码"}}

  - path: /etf-flow
    method: GET
    desc: ETF 三信号（份额/北向/主力，Tushare）
    mcp: {expose: true, tool_name: get_etf_flow, sample: none}
    params: {symbol: {type: str, default: "510880"}, start: {type: date}, end: {type: date}}

  # ===== 事件冲击产业链（只暴露只读子集）=====
  - path: /event/themes
    method: GET
    desc: 全部事件主题模板
    mcp: {expose: true, tool_name: get_event_themes, sample: none}

  - path: /event/themes/{theme_id}
    method: GET
    desc: 主题详情（含成分股）
    mcp: {expose: true, tool_name: get_event_theme_detail, sample: none}
    params: {theme_id: {type: int, required: true}}

  - path: /event/llm-config
    method: GET
    desc: LLM 配置状态
    mcp: {expose: false, hide_reason: "含 api_key 掩码，配置类不暴露"}

  - path: /event/llm-config
    method: PUT
    desc: 设置 LLM 配置
    mcp: {expose: false, hide_reason: "敏感配置写入"}

  - path: /event/smart-match
    method: POST
    desc: LLM 智能匹配事件标的
    mcp: {expose: false, hide_reason: "LLM-in-LLM 放大延迟与成本，且需先配 LLM"}

  - path: /event/concept-stocks
    method: GET
    desc: 拉概念板块成分股
    mcp: {expose: false, hide_reason: "实时拉数慢，且为 smart-match 的辅助接口"}

  - path: /event
    method: POST
    desc: 创建事件
    mcp: {expose: false, hide_reason: "写操作"}

  - path: /event/{event_id}
    method: GET
    desc: 事件详情
    mcp: {expose: true, tool_name: get_event_detail, sample: none}
    params: {event_id: {type: int, required: true}}

  - path: /event/{event_id}/stocks
    method: PUT
    desc: 更新事件标的池
    mcp: {expose: false, hide_reason: "写操作"}

  - path: /event/{event_id}/impact
    method: GET
    desc: 事件冲击三视图（归一化收益+涨跌排行+相关性热力图）
    mcp: {expose: true, tool_name: get_event_impact, sample: event_impact}
    params: {event_id: {type: int, required: true}, before: {type: int, default: 20, desc: "事件前窗口 0-120"}, after: {type: int, default: 20, desc: "事件后窗口 0-120"}}

  # ===== 擂台 =====
  - path: /arena/compare
    method: GET
    desc: 策略横向对比（cross_strategy / cross_symbol）
    mcp: {expose: true, tool_name: compare_strategies, sample: chart80}
    params: {mode: {type: str, required: true, desc: "cross_strategy（同标的多策略）或 cross_symbol（同策略多标的）"}, symbol: {type: str, desc: "cross_strategy 模式必填"}, strategy: {type: str, desc: "cross_symbol 模式必填"}, symbols: {type: list, desc: "cross_symbol 模式下的标的列表"}, start: {type: date}, end: {type: date}}

  # ===== 反馈（全部隐藏）=====
  - path: /feedback
    method: POST
    desc: 提交反馈
    mcp: {expose: false, hide_reason: "反馈系统，与 LLM 分析无关"}

  - path: /feedback
    method: GET
    desc: 反馈列表
    mcp: {expose: false, hide_reason: "同上"}

  - path: /feedback/{fb_id}
    method: DELETE
    desc: 删除反馈
    mcp: {expose: false, hide_reason: "写操作 + 与分析无关"}

  # ===== MCP 状态（Part C，前端用；不暴露给 MCP 自身避免循环）=====
  - path: /mcp/status
    method: GET
    desc: MCP server 连接状态（供前端状态面板）
    mcp: {expose: false, hide_reason: "MCP 自举状态接口，暴露给 MCP 自身是循环依赖；仅供前端面板调用"}
    params: {}
    notes: "Part C 新增。返回 {enabled, mcp_url, backend_reachable, tool_count, tools[], last_check}"
```

### 暴露统计

- **expose=true：30 个**（系统 5 + 市场/估值 5 + 回测创建 5 + 回测查询 10 + drawboard 交互 2 + 事件只读 4 + 擂台 1，含 2 个 drawboard chart/summary，实际清单见 Part A 第 6 节）
- **expose=false：21 个**（数据/配置 5 + 各 preview 4 + event 配置/写/智能匹配 6 + feedback 3 + 旧 valuation 1 + drawboard 无 + portfolio 无）

> 注：024 估值 v2 的三条端点（indices/single/overlay）已在表中预填 `expose=true`，但标注「024 交付后启用」——026 实施时若 024 未交付，临时改为 `expose=false` 或临时指向旧 `/valuation` 端点。

### 契约表的使用流程

1. **backend 新增接口**：开发者在本表加一条记录，填 `mcp.expose` 决定是否暴露。
2. **MCP server 启动**：读本表 → 对 `expose=true` 的接口注册 tool（参数从 `params` 或 `params_ref` 取）→ 对 `sample=chart80` 的接口套降采样。
3. **校验（可选，开放问题）**：`scripts/check_api_registry.py` 扫 `backend/app/api/*.py` 的 `@router.*` 装饰器，与本表 path/method 对比，报告「backend 有但表里缺」「表里有但 backend 没有」的漂移。CI 跑此脚本防漂移。

### 治理演进路线

- **本期（方案 2）**：YAML 人工维护 + 可选漂移检查脚本。
- **未来（方案 3，列为开放问题）**：backend 路由装饰器加自定义元数据（如 `@router.get(..., expose_mcp=True, mcp_sample="chart80")`），MCP 启动时 import 路由表自动生成 tool 清单 + 参数 schema（直接从 Pydantic 模型抽）。彻底消除双份维护，但要改 backend 代码且引入 mcp_server → backend 的跨包依赖。本期不做。

---

## Part A：MCP Server 实现

### 1. 目录结构

```
mcp_server/
├── pyproject.toml              # 独立依赖：fastmcp + httpx（不依赖 fastapi/sqlalchemy/akshare）
├── .env.example                # PORTLAB_API_BASE, MCP_HTTP_PORT
├── README.md                   # 启动方式 + ZCode/客户端配置示例
├── Dockerfile                  # python:3.12-slim（与 backend 同款基础镜像）
├── src/
│   └── portlab_mcp/
│       ├── __init__.py
│       ├── server.py           # FastMCP 实例 + HTTP 传输启动入口
│       ├── client.py           # 单例 httpx.AsyncClient + call() 统一解包 ApiResponse
│       ├── config.py           # pydantic-settings 读 PORTLAB_API_BASE / MCP_HTTP_PORT
│       ├── registry_loader.py  # 解析 api-registry.yaml → ToolSpec 列表
│       ├── transforms.py       # chart 降采样 + 通用裁剪
│       └── tools/
│           ├── __init__.py     # register_all(mcp, client, registry)
│           ├── system.py       # health/roadmap/release-notes/recent/symbols
│           ├── market.py       # market-overview/etf-flow/valuation-*
│           ├── backtest.py     # dca/ma120/grid/portfolio 创建 + chart(降采样) + summary
│           ├── drawboard.py    # series/realtime/save + chart + summary
│           ├── event.py        # themes/theme-detail/event-detail/impact（只读）
│           └── arena.py        # compare
└── tests/
    ├── test_transforms.py      # 降采样逻辑单测
    └── test_registry.py        # 契约表解析单测
```

> 前端另有 `frontend/src/components/McpStatusButton.vue` + `McpStatusPanel.vue`（Part C），不在此目录树。

### 2. `pyproject.toml`（独立）

```toml
[project]
name = "portlab-mcp"
version = "0.1.0"
description = "PortLab MCP Server —— 把 PortLab API 暴露给 LLM"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=2.0",
    "httpx>=0.27",
    "pydantic>=2.5",
    "pydantic-settings>=2.5",
    "pyyaml>=6.0",
    "anyio>=4",
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-asyncio>=0.23"]

# 不声明 [build-system]：uv 视为虚拟项目（与 backend 风格一致）
```

**关键设计**：**不 import backend 代码**。理由：
- 拉进 `fastapi/sqlalchemy/pymysql/akshare/tushare/scipy` 会让 MCP server 依赖半个 backend，违背「独立轻量」初衷。
- Tool 入参 schema 在 mcp_server 侧重新定义为精简 Pydantic 模型，从 `api-registry.yaml` 的 `params` 字段生成。
- 代价：schema 双份维护（backend `schemas/*.py` ↔ registry YAML），但 YAML 是契约表本就要维护，漂移检查脚本兜底。

### 3. `docker-compose.yml` 新增 mcp 服务

```yaml
  mcp:
    build: ./mcp_server
    container_name: portlab-mcp
    restart: unless-stopped
    environment:
      PORTLAB_API_BASE: http://backend:8010/api    # 容器间走服务名
      MCP_HTTP_PORT: "8020"
    ports:
      - "8020:8020"
    depends_on:
      - backend
    volumes:
      - ./docs/api-registry.yaml:/app/api-registry.yaml:ro   # 挂载契约表（只读）
      - ./mcp_server:/app
      - /app/.venv
    command: [".venv/bin/python", "-m", "portlab_mcp.server"]
```

- 宿主机访问：`http://localhost:8020/mcp`（FastMCP Streamable HTTP 默认路径）。
- 契约表挂载为只读卷，改 YAML 后重启 mcp 容器即生效（无需重新构建镜像）。

### 4. 核心代码骨架

#### 4.1 `client.py` — HTTP 桥接 + ApiResponse 解包

```python
import httpx
from typing import Any

class PortLabClient:
    """单例 HTTP client，统一解包 ApiResponse 信封。"""
    def __init__(self, base_url: str):
        self._http = httpx.AsyncClient(base_url=base_url, timeout=60.0)

    async def call(self, method: str, path: str, **kwargs) -> Any:
        """调 backend，返回 ApiResponse.data；code≠0 抛 ValueError。"""
        r = await self._http.request(method, path, **kwargs)
        r.raise_for_status()
        payload = r.json()
        if payload.get("code") != 0:
            raise ValueError(f"PortLab API 错误: {payload.get('message', '未知错误')}")
        return payload.get("data")

    async def close(self):
        await self._http.aclose()
```

- `timeout=60.0`：覆盖 `/event/{id}/impact`（拉多标的行情）和回测创建的拉数延迟。

#### 4.2 `server.py` — FastMCP + HTTP 传输

```python
from fastmcp import FastMCP
from .client import PortLabClient
from .config import settings
from .registry_loader import load_registry
from .tools import register_all

mcp = FastMCP("PortLab")
mcp.instructions = (
    "PortLab 是 A 股投资分析工具箱。可用能力：查指数估值（PE 通道/分位/多指数叠加）、"
    "跑回测（定投/MA120/网格/组合/回撤买入）、看市场概览与 ETF 资金流、"
    "分析事件冲击产业链、横向对比策略。"
    "回测流程：先 run_*_backtest 拿 task_id，再 get_*_summary 看指标，get_*_chart 看曲线（已降采样）。"
)

client: PortLabClient | None = None

def start():
    global client
    client = PortLabClient(settings.PORTLAB_API_BASE)
    registry = load_registry("/app/api-registry.yaml")
    register_all(mcp, client, registry)
    mcp.run(transport="http", host="0.0.0.0", port=settings.MCP_HTTP_PORT)

if __name__ == "__main__":
    start()
```

#### 4.3 `transforms.py` — chart 降采样（核心）

```python
def downsample_chart(chart: dict, target_points: int = 80) -> dict:
    """把 chart 的并列数组降采样到 ~target_points 点。

    策略：
    1. 以 dates 数组长度 N 为基准（所有并列数组同长）。
    2. N <= target_points 直接返回原数据。
    3. 否则等间隔采样 + 强制保留首尾索引。
    4. 强制保留所有 buy_points/sell_points 的日期索引（信号日不能丢）。
    5. 对所有 list[标量] 且长度 == N 的字段用同一索引集切片。
    6. 嵌套对象（buy_points/sell_points/correlation_matrix/frontier）不降采样。
    7. 返回新 dict，加 _meta: {original_len, sampled_len, sampled: True}。
    """
    dates = chart.get("dates", [])
    n = len(dates)
    if n <= target_points:
        return chart

    # 采样索引集
    step = max(1, n // target_points)
    indices = set(range(0, n, step))
    indices.add(0)
    indices.add(n - 1)
    # 并入信号日
    date_to_idx = {d: i for i, d in enumerate(dates)}
    for key in ("buy_points", "sell_points"):
        for pt in chart.get(key, []):
            if pt.get("date") in date_to_idx:
                indices.add(date_to_idx[pt["date"]])
    indices = sorted(indices)

    out = {}
    for k, v in chart.items():
        if k in ("buy_points", "sell_points"):
            out[k] = v  # 子对象数组不降采样
        elif isinstance(v, list) and len(v) == n and v and not isinstance(v[0], (list, dict)):
            out[k] = [v[i] for i in indices]  # 并列标量数组按索引切片
        else:
            out[k] = v  # 嵌套矩阵/对象/标量不动
    out["_meta"] = {"original_len": n, "sampled_len": len(indices), "sampled": True}
    return out
```

- 处理所有 chart 类 tool：dca/ma120/grid/portfolio/drawboard 的 chart、drawboard series、valuation overlay、arena compare。
- `portfolio.chart` 的 `correlation_matrix`（n×n）、`frontier`（嵌套对象）跳过；`nav/drawdown/benchmark_nav` 按索引切片。
- `arena.compare` 的多条归一化曲线按同一索引集切片。

#### 4.4 `registry_loader.py` — 解析契约表

```python
import yaml
from dataclasses import dataclass

@dataclass
class ToolSpec:
    tool_name: str
    method: str
    path: str
    desc: str
    sample: str          # none / chart80 / summary_only / event_impact
    params: dict         # 参数定义（从 YAML params 或 params_ref 推导）

def load_registry(path: str) -> list[ToolSpec]:
    with open(path) as f:
        doc = yaml.safe_load(f)
    out = []
    for ep in doc["endpoints"]:
        mcp = ep.get("mcp", {})
        if not mcp.get("expose"):
            continue
        out.append(ToolSpec(
            tool_name=mcp["tool_name"],
            method=ep["method"],
            path=ep["path"],
            desc=ep["desc"],
            sample=mcp.get("sample", "none"),
            params=ep.get("params") or _resolve_params_ref(ep.get("params_ref")),
        ))
    return out
```

- `params_ref`（如 `app.schemas.ma120.Ma120Request`）一期在 mcp 侧硬编码对应 dict（避免 import backend），二期再考虑从 backend 抽。

### 5. Tool 注册模式（以 ma120 为例）

每个 tool 一个装饰器，按 registry 动态生成或手工写。手工写更清晰可控：

```python
# tools/backtest.py
from fastmcp import FastMCP
from ..client import PortLabClient
from ..transforms import downsample_chart

def register_backtest(mcp: FastMCP, client: PortLabClient):
    @mcp.tool()
    async def run_ma120_backtest(
        symbol: str, start_date: str, end_date: str,
        capital_mode: str = "fixed", principal: float | None = None,
        monthly_amount: float | None = None, splits: int = 10,
        ma_period: int = 120, buy_threshold: float = 0.985,
        step: float = 0.01, crash_threshold: float = 0.05,
        crash_multiplier: int = 2, sell_mode: str = "batch",
        batch_sell_step: float = 0.02, dividend_mode: str = "cash",
    ) -> dict:
        """运行 MA120 策略回测，返回 {task_id}。
        symbol: 6 位代码如 510880；capital_mode: fixed/recurring/hybrid；
        sell_mode: batch/all/half。其余参数见 PortLab 文档。"""
        body = {k: v for k, v in locals().items() if v is not None}
        return await client.call("POST", "/backtest/ma120", json=body)

    @mcp.tool()
    async def get_ma120_chart(task_id: str) -> dict:
        """取 MA120 回测图表（已降采样到 ~80 点，保留买卖信号日）。"""
        data = await client.call("GET", f"/backtest/ma120/{task_id}/chart")
        return downsample_chart(data, target_points=80)

    @mcp.tool()
    async def get_ma120_summary(task_id: str) -> dict:
        """取 MA120 回测汇总指标（投入/收益/年化/回撤/胜率/买卖次数）。"""
        return await client.call("GET", f"/backtest/ma120/{task_id}/summary")
```

### 6. 暴露的 tool 完整清单（30 个，对应契约表 expose=true）

**系统/元信息（5）**：`health_check` / `get_roadmap` / `get_release_notes` / `get_recent_backtests` / `search_symbols`

**市场/估值（5）**：`get_market_overview` / `get_etf_flow` / `get_valuation_indices` / `get_valuation_single` / `get_valuation_overlay`

**回测创建（5）**：`run_dca_backtest` / `run_ma120_backtest` / `run_grid_backtest` / `run_portfolio_backtest` / `save_drawboard_backtest`

**回测结果查询（10，chart 走降采样）**：`get_dca_chart` / `get_dca_summary` / `get_ma120_chart` / `get_ma120_summary` / `get_grid_chart` / `get_grid_summary` / `get_portfolio_chart` / `get_portfolio_summary` / `get_drawboard_chart` / `get_drawboard_summary`

**drawboard 交互（2）**：`get_drawboard_series` / `run_drawboard_realtime`

**事件只读（4）**：`get_event_themes` / `get_event_theme_detail` / `get_event_detail` / `get_event_impact`

**擂台（1）**：`compare_strategies`

### 7. 隐藏的 21 个接口（逐条理由见契约表 `hide_reason`）

- 数据/配置（5）：`POST /data/fetch`、`GET /datasource/status`、`PUT/DELETE /datasource/token`、`PUT /datasource/toggle`
- 各 preview（4）：dca/ma120/grid 的 preview（与创建重复，但 control flow 正常可作实现参考）
- event 配置/写/智能匹配（6）：`GET/PUT /event/llm-config`、`POST /event/smart-match`、`GET /event/concept-stocks`、`POST /event`、`PUT /event/{id}/stocks`
- feedback（3）：`POST/GET /feedback`、`DELETE /feedback/{id}`
- 旧 valuation（1）：`GET /valuation`（被 /single 取代）

### 8. 错误处理与边界

- **backend 不可达**：`httpx.ConnectError` 由 FastMCP 转 tool error，附提示「PortLab 后端未启动，请 `docker compose up backend`」。
- **ApiResponse code≠0**：抛 ValueError，把 backend 的中文 message 给 LLM（如「未找到回测任务 xxx」「该指数无 PE 数据」）。
- **chart 降采样后仍超限**（极端 20 年区间）：二次降采样到 40 点。
- **参数校验失败**：backend 已转 `code:1` + 中文 message，MCP 透传，LLM 据此修正参数重试。

### 验收标准（Part A）

- [ ] `mcp_server/` 独立目录、独立 pyproject、独立 Dockerfile
- [ ] `docker compose up mcp` 能起，端口 8020 的 `/mcp` 可达
- [ ] `mcp.run(transport="http")` 正常启动，无 import backend 代码
- [ ] 契约表 `docs/api-registry.yaml` 覆盖全部 51 接口，expose=true 的 30 个
- [ ] 30 个 tool 注册成功，每个 description 清晰（LLM 能据此决定何时调）
- [ ] `health_check` / `get_roadmap` 等简单 GET tool 能返回数据
- [ ] `run_ma120_backtest` → `get_ma120_summary` → `get_ma120_chart` 链路通（需 025 修完控制流 bug 后）
- [ ] chart 降采样生效：mock 2500 点输入 → 输出 ≤80 点，首尾 + 买卖信号日保留
- [ ] 隐藏接口（21 个）不在 tool 列表
- [ ] backend 宕机时 tool 调用返回友好错误而非进程崩溃
- [ ] README 含 ZCode 配置示例和启动步骤
- [ ] `tests/test_transforms.py` + `tests/test_registry.py` 通过

---

## Part B：文档与示例

### 1. `mcp_server/README.md`

- 启动方式：`docker compose up mcp` 或本地 `uv run python -m portlab_mcp.server`
- 环境变量：`PORTLAB_API_BASE`（默认 `http://localhost:8010/api`）、`MCP_HTTP_PORT`（默认 8020）
- 客户端配置示例（ZCode / Claude Desktop / 任意 MCP 客户端）
- 30 个 tool 的分类索引 + 典型用法示例
- 契约表维护说明：新增接口时如何更新 `docs/api-registry.yaml`

### 2. ZCode 客户端配置（README 示例）

```json
{
  "mcpServers": {
    "portlab": {
      "url": "http://localhost:8020/mcp"
    }
  }
}
```

### 3. 使用示例（写入 README）

**示例 1：查估值**
> 用户：「沪深300 现在贵不贵？」
> LLM 调 `get_valuation_single(symbol="000300", lookback="5y")` → 返回 PE 通道 + 分位 → LLM 解读「当前 PE 12.3，5 年分位 35%，偏低估区」

**示例 2：跑回测**
> 用户：「510880 过去 3 年 MA120 策略表现如何？」
> LLM 调 `run_ma120_backtest(symbol="510880", start_date="2023-01-01", end_date="2026-07-27")` → 拿 task_id → `get_ma120_summary(task_id)` → 解读「年化 8.2%，最大回撤 12%，胜率 60%」→ 必要时 `get_ma120_chart(task_id)` 看曲线

**示例 3：对比策略**
> 用户：「510880 上定投和 MA120 哪个好？」
> LLM 调 `compare_strategies(mode="cross_strategy", symbol="510880")` → 拿归一化净值对比

### 验收标准（Part B）

- [ ] README 启动/配置/示例齐全
- [ ] 30 tool 分类索引可查
- [ ] 契约表维护流程有文字说明

---

## Part C：前端 MCP 状态面板（导航栏右上角）

让用户在 UI 上直接感知「项目已 MCP 化」并一键拿到连接配置，不必翻文档找端口和 URL。**放在「问题反馈」图标的左侧**。

### 1. 触发图标（SVG）

固定用用户提供的这个 MCP 风格 SVG（两道波浪线，识别度高）：

```html
<svg viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" width="200" height="200">
  <path d="M580.5056 135.8336c24.576 0 48.128 9.5744 65.7408 26.6752 35.584 34.6624 36.3008 91.648 1.6384 127.232l-1.536 1.536-264.7552 259.7888a29.99296 29.99296 0 0 0-0.512 42.3936l0.512 0.512a31.34464 31.34464 0 0 0 43.776 0l3.584-3.5328 261.2224-256.256c36.608-35.5328 94.8736-35.4816 131.3792 0.1024l1.8432 1.8432c35.584 34.6624 36.352 91.648 1.6384 127.232l-1.6384 1.6384-317.0816 310.8864c-27.6992 26.8288-28.3648 71.0656-1.536 98.7648l1.536 1.536 65.0752 63.7952c12.4416 12.032 32.3584 11.7248 44.3904-0.7168 2.56-2.6624 4.6592-5.7344 6.144-9.1136 4.8128-11.3664 2.1504-24.5248-6.7072-33.1264l-65.1264-63.8976c-3.9424-3.84-4.0448-10.1376-0.2048-14.08l0.2048-0.2048 317.0304-310.8864c59.3408-57.7536 60.5696-152.6784 2.816-212.0192-0.9216-0.9728-1.8432-1.8432-2.816-2.816l-1.8432-1.8432a156.52352 156.52352 0 0 0-131.4304-42.9568 149.7088 149.7088 0 0 0-43.8784-128.8704c-60.9792-59.2896-158.0544-59.2896-219.0336 0L120.576 463.2576a29.94688 29.94688 0 0 0-0.5632 42.3936l0.5632 0.5632a31.4368 31.4368 0 0 0 43.776 0l350.5152-343.7056a94.208 94.208 0 0 1 65.6896-26.6752z"></path>
  <path d="M609.1776 238.592c-1.5872 3.6864-3.84 7.0656-6.7584 9.8304L343.296 502.6816c-35.584 34.6624-36.3008 91.648-1.6384 127.232 0.5632 0.5632 1.0752 1.1264 1.6384 1.6384 36.5568 35.584 94.8224 35.584 131.3792 0l259.1744-254.2592c12.4416-12.1344 32.3584-11.8272 44.4928 0.6144 2.6112 2.6624 4.7104 5.7856 6.2464 9.216 4.8128 11.3664 2.0992 24.576-6.8096 33.1264l-259.2768 254.2592c-60.9792 59.3408-158.1056 59.3408-219.0848 0-59.2896-57.6512-60.672-152.4224-3.0208-211.7632 0.9728-1.024 1.9968-2.048 3.0208-3.0208l259.2256-254.2592a31.40096 31.40096 0 0 1 50.5856 9.8304c3.1232 7.424 3.1232 15.872 0 23.296h-0.0512z"></path>
</svg>
```

图标按导航栏现有尺寸缩放（约 20×20，`color: currentColor`），点击打开状态面板。与「问题反馈」「更新日志」同款交互（按钮 + 浮层/弹窗）。

### 2. 状态面板布局（`McpStatusPanel.vue`）

```
┌──────────────────────────────────────────┐
│  MCP Server                              │
├──────────────────────────────────────────┤
│  状态  ● 运行中 / ○ 未启动                │  ← 绿点/灰点
│                                          │
│  连接地址  http://localhost:8020/mcp      │  ← 一键复制按钮
│                                          │
│  后端连通  ✓ 正常 / ✗ 不可达              │
│                                          │
│  已暴露工具  30 个                        │
│    ［展开/折叠查看 tool 列表］            │  ← 分类：系统/市场/回测/事件
│                                          │
│  最近检查  2026-07-27 14:32:11           │
├──────────────────────────────────────────┤
│  [复制 ZCode 配置]  [关闭]                │  ← 复制 mcpServers JSON
└──────────────────────────────────────────┘
```

**面板项**：
- **状态灯**：绿点（运行中）/ 灰点（未启动）。判定依据 `enabled && backend_reachable`。
- **连接地址**：MCP server 的 HTTP 端点（`http://localhost:8020/mcp`），右侧 📋 一键复制。
- **后端连通**：MCP server 探测 backend 是否可达（`backend_reachable`）。
- **已暴露工具数 + 可展开列表**：从 MCP server 拉的 `tools[]`（按 registry 分组）。
- **最近检查时间**：`last_check`（前端每次打开面板时刷新）。
- **复制 ZCode 配置按钮**：生成 `{"mcpServers":{"portlab":{"url":"..."}}}` JSON 写剪贴板，方便用户粘到 ZCode 配置。

### 3. 数据来源：新增 `/api/mcp/status` 端点

前端面板调 backend 的 `GET /api/mcp/status`（**不经过 MCP server**，直接调 backend；backend 转发探测 mcp 容器）。

**为什么走 backend 而非前端直连 mcp 容器**：
- 前端浏览器直连 `localhost:8020/mcp` 会触发 MCP 协议握手（Streamable HTTP），不是简单 REST，不适合浏览器 fetch。
- backend 作为代理：自己 httpx 探测 mcp 容器的健康端点，把结果汇总成 REST 响应给前端。

**返回结构**：
```json
{
  "code": 0,
  "data": {
    "enabled": true,
    "mcp_url": "http://localhost:8020/mcp",
    "backend_reachable": true,
    "tool_count": 30,
    "tools": [
      {"name": "health_check", "group": "system", "desc": "健康检查"},
      {"name": "run_ma120_backtest", "group": "backtest", "desc": "创建 MA120 回测"}
    ],
    "last_check": "2026-07-27T14:32:11+08:00"
  }
}
```

**backend 实现**（`backend/app/api/mcp.py` 新建）：
- 读 `PORTLAB_MCP_URL` 环境变量（compose 注入，默认 `http://mcp:8020/mcp`）。
- httpx 探测 mcp 容器：FastMCP 暴露 `/.well-known/` 或自定义 `/healthz`（在 mcp server 加一个轻量健康路由，不走 MCP 协议）。
- tool 列表：mcp server 的 `/healthz` 顺带返回已注册 tool 清单（registry 里 expose=true 的）。
- backend 探测失败时返回 `enabled=false, backend_reachable=true`（backend 自己可达，但 mcp 容器没起）。

**注册到 main.py**：`app.include_router(mcp.router, prefix="/api/mcp", tags=["mcp"])`。

> **契约表已登记**：`/mcp/status` 标 `expose=false`（MCP 不暴露自己的状态接口，避免循环依赖；仅供前端面板调用）。

### 4. 前端组件

- `frontend/src/components/McpStatusButton.vue`：导航栏图标按钮，内嵌上面的 SVG，点击 emit/open 面板。
- `frontend/src/components/McpStatusPanel.vue`：状态面板（弹窗或下拉浮层），调 `getMcpStatus()` 拉数据，渲染状态灯/地址/工具列表/复制按钮。
- `frontend/src/api/index.ts`：新增 `getMcpStatus()` → GET `/api/mcp/status` + `McpStatusData` 类型。
- `frontend/src/App.vue`：在 `<nav>` 的「问题反馈」图标**左侧**插入 `<McpStatusButton />`。

### 5. 交互与样式

- 与「问题反馈」「更新日志」图标同款：固定图标按钮 + 浮层；明暗主题适配。
- 复制按钮成功后 toast「已复制」（复用 010 的 toast 机制）。
- 状态灯颜色：绿 `#3ba272`（运行中）/ 灰 `#8a8f99`（未启动）/ 黄 `#faad14`（mcp 起了但 backend 不通）。
- tool 列表默认折叠，点「展开」按分组显示 30 个 tool 名 + 描述。
- 面板每次打开重新调 `/api/mcp/status`（不缓存，反映实时状态）。

### 验收标准（Part C）

- [ ] 导航栏「问题反馈」左侧出现 MCP 图标（指定 SVG）
- [ ] 点击图标打开状态面板
- [ ] 面板显示状态灯、连接地址（可一键复制）、后端连通、工具数 + 可展开列表、最近检查时间
- [ ] 「复制 ZCode 配置」按钮生成正确 JSON 并写入剪贴板
- [ ] mcp 容器未启动时状态灯灰、地址仍显示、工具数为 0
- [ ] backend 不可达时状态灯黄
- [ ] 明暗主题切换样式正确
- [ ] `/api/mcp/status` 端点返回完整字段
- [ ] 契约表已登记 `/mcp/status`（expose=false）

---

## 数据复用与隔离策略

| 数据/能力 | 来源 | MCP 处理 |
|-----------|------|----------|
| 51 个 HTTP 接口 | backend 已有 | HTTP 桥接，零数据迁移 |
| ApiResponse 信封 | backend 已有 | client.call 统一解包 |
| Pydantic schema | backend 已有 | mcp 侧重定义精简版（从 YAML 生成） |
| 契约表 | `docs/api-registry.yaml` 新建 | 单一事实源，挂载进容器 |
| chart 降采样 | mcp 侧 transforms.py | 不改 backend，纯出站裁剪 |

> MCP server 是纯「消费层 + 裁剪层」，不改 backend 任何代码、不直接连 DB、不 import backend 模块。所有数据通过 HTTP 从 backend 取。

---

## 开放问题（后续迭代）

- [ ] **方案 3：路由装饰器自动生成契约**（替代手写 YAML）。backend 路由加 `expose_mcp=True` 元数据，MCP 启动时 import 路由表 + Pydantic schema 自动生成 tool。彻底消除双份维护，但需改 backend 且引入跨包依赖。本期 YAML 是过渡态。
- [ ] **漂移检查脚本** `scripts/check_api_registry.py`：扫 backend `@router.*` 与 YAML 对比，CI 防漂移。
- [ ] **tool 级 rate-limit**：一期靠隐藏 `/data/fetch` 规避；若 LLM 高频调回测创建触发限频，再加 tool 级节流。
- [ ] **stdio 传输支持**：本期只 HTTP；未来若需本地 ZCode 直连（免去 HTTP 跳转），加 `mcp.run(transport="stdio")` 分支。
- [ ] **SSE 推送**：若 backend 未来加长任务（如回测进度），MCP 可用 SSE 流式返回。当前回测都是同步的，不需要。
- [ ] **认证层**：若 backend 未来加 API key，MCP client.call 注入 `Authorization` 头即可，不影响 tool 定义。
- [ ] **024 估值 v2 端点激活**：024 交付后，移除契约表里三条 valuation 端点的「024 交付后启用」注释。

---

## 顺带观察（已在 025 单独处理）

`backend/app/api/` 下多个 POST 创建类接口曾有「幂等命中检查后的 return 语句未缩进进 if 块内、导致后续补数据/计算/落库代码不可达」的同源 bug——`backtest.py` 的 DCA 创建已于 commit `2859567`（2026-07-27）修复，**剩余 3 处（ma120 / grid / drawboard）由 [025 — 修复 POST 创建接口控制流 bug](./025-fix-post-create-bug.md) 系统性修复**。本任务（026 MCP）依赖 025 完成后才能验收回测创建链路。契约表 `notes` 字段已逐条标注修复状态。
