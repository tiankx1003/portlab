# PortLab — 个人投资分析工具箱

PortLab 是一个本地部署的个人投资分析平台：**定投回测、MA120 红利策略、回撤买入、网格交易、组合回测（有效前沿）、策略擂台、ETF 资金流向、估值看板、事件冲击产业链、市场概览**，并支持 **AkShare / Tushare 双数据源**一键切换。前后端 + MySQL 全部 Docker Compose 一键启停。另内置 **MCP Server**（独立容器），把 32 个核心 API 暴露给 LLM（ZCode / Claude），在对话里直接查估值、跑回测、分析事件冲击。

## 功能一览

| 模块 | 说明 |
|------|------|
| **定投回测**（普通 / 智能均线） | 选标的、频率、金额、区间，逐日算市值/成本/盈亏/收益率；智能模式按均线偏离度动态扣款。XIRR 年化 + 最大回撤 + 双轴图表。支持「预览」实时算 + 「保存」落库两段式。 |
| **MA120 红利策略** | 价格跌破 MA120 × 阈值金字塔分批买入，站回 MA 上方分批/全部/半仓兑现；固定本金 / 每月投入 / 混合三种资金模式，复利再投开关。 |
| **回撤买入策略看板** | 拖动「回撤阈值」实时定义买点：回撤达阈值首买、每再多跌 N% 加仓、新高/部分清仓；左轴价格/回撤镜像 + 右轴市值/收益。 |
| **网格交易策略回测** | 中枢 + 间距双向触发吃震荡：价格每跌一档买入、每涨一档卖出，画网格 markLine；补齐趋势/恐慌/震荡三件套。 |
| **组合回测（含有效前沿）** | 多标的组合收益/回撤/波动 + 马科维茨有效前沿求最优权重（最小方差 / 最大夏普），含相关性热力图。 |
| **策略擂台（横向对比）** | 同标的多策略 / 同策略多标的对比，归一化净值叠加 + 指标表，消费四策略 summary。 |
| **估值看板** | 7 指数（lg + csindex 双源）PE 历史分位 + **PE 估值通道**（5 条线分高估/中性/低估带）+ 多指数 PE 归一化叠加 + 时间窗口；4 个无数据指数灰显。 |
| **ETF 资金流向** | 份额变动 + 北向资金两路信号（Tushare），观察机构 / 国家队动向。 |
| **事件冲击产业链看板** | 事件 → 标的池 → 产业链关系图 + 波动对比 + 相关性热力图；LLM 智能匹配（OpenAI 兼容协议）。 |
| **市场概览** | 预置指数（沪深300 / 红利ETF / 红利低波）最新价 + 涨跌幅 + 迷你 sparkline，第 4 格可手动输入代码，一键刷新。 |
| **首页门户** | 功能入口卡片、最近回测记录（点击直达结果）、最近更新、Roadmap；品牌区可点击回首页。 |
| **数据源切换** | 右上角钥匙图标：默认 AkShare 免费；开启 Tushare 后行情独立成表、互不污染。Token 持久化、重启不丢。 |
| **更新日志 / 反馈 / GitHub** | 导航栏铃铛看最新迭代、反馈图标提建议、GitHub 外链。 |
| **MCP Server（LLM 接入）** | 独立容器（`mcp_server/`）把 32 个核心 API 暴露为 MCP tool（只读查询 + 回测创建，chart 自动降采样到 ~80 点）；导航栏 MCP 图标看连接状态 / 工具清单 / 一键复制 ZCode 配置。契约表 `docs/api-registry.yaml` 治理接口暴露与漂移。 |

## 技术栈

| 组件 | 选择 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.x |
| 数据库 | MySQL 8.x |
| 前端 | Vue 3 + Vite + ECharts 5 + Vue Router + Axios |
| 数据源 | AkShare（默认，东财优先 + 腾讯回退）/ Tushare Pro（可选） |
| MCP | FastMCP（Streamable HTTP），独立容器，仅 fastmcp + httpx |
| 包管理 | uv（后端 / mcp）/ npm（前端） |
| 部署 | Docker Compose 一键启停（mysql + backend + mcp + frontend） |

## 快速启动

```bash
# 1. 准备环境变量（可选，文件内含默认值可直接用）
cp .env.example .env

# 2. 一键构建并启动 mysql + backend + mcp + frontend
docker compose up -d --build

# 3. 验证
curl http://localhost:8010/api/health   # {"code":0,"message":"success","data":{"status":"ok"}}
curl http://localhost:8020/healthz      # MCP server：{"status":"ok","tool_count":32,...}
```

启动后访问：

- 前端：http://localhost:5173（端口可由 `.env` 的 `VITE_PORT` 配置）
- 后端 API / Swagger 文档：http://localhost:8010/docs
- MCP Server（LLM 连）：http://localhost:8020/mcp （Streamable HTTP）

**启用 Tushare（可选）**：在前端右上角钥匙图标面板填入 [Tushare Pro Token](https://tushare.pro/register) 并打开开关；或在 `.env` 设 `TUSHARE_TOKEN`。开关关闭即回退 AkShare 免费数据，Token 保留不删。

> **首次拉取基础镜像提示**：若 `docker compose up` 因拉不到 `mysql` / `python` / `node` 镜像失败（Docker Hub 不可达），可经国内镜像源拉取并重打 tag，例如：
> ```bash
> docker pull docker.m.daocloud.io/library/mysql:8.4 && docker tag docker.m.daocloud.io/library/mysql:8.4 mysql:8.4
> # 同理处理 python:3.12-slim、node:20-alpine
> ```
> 随后再次执行 `docker compose up -d --build`。

## 本地开发指南

### 后端（不依赖 Docker）

```bash
cd backend
uv sync                     # 安装依赖
uv run uvicorn app.main:app --reload --port 8010
```

需配置数据库连接（环境变量或 `.env`）：`DB_HOST` `DB_PORT` `DB_USER` `DB_PASS` `DB_NAME`。

### 前端

```bash
cd frontend
npm install
npm run dev                 # http://localhost:5173 ，/api 默认代理到 http://localhost:8010
```

本地裸跑前后端时，前端 dev server 的端口、后端代理目标、host 白名单均可通过环境变量配置（见 `.env` 的 `VITE_PORT` / `VITE_BACKEND_TARGET` / `VITE_ALLOWED_HOSTS`）：容器内默认端口 5173、代理 `http://backend:8010`，裸跑时把代理改 `http://127.0.0.1:8010`。

### MCP Server（可选，LLM 接入）

```bash
cd mcp_server
uv sync
PORTLAB_API_BASE=http://localhost:8010/api \
MCP_REGISTRY_PATH=../docs/api-registry.yaml \
uv run python -m portlab_mcp.server   # http://localhost:8020/mcp
```

### 数据库

首次启动由 `mysql/init/*.sql` 自动建库建表（已部署库升级用 `mysql/migrations/*.sql`）。表命名约定：

- `raw_*` —— 原始拉取数据（`raw_price_daily` AkShare / `raw_price_daily_tushare` Tushare）
- `calc_*` —— 计算中间结果（`calc_dca_backtest` / `calc_ma120_backtest`）
- `result_*` —— 最终输出（`result_dca_summary` / `result_ma120_summary`）
- `data_source_config` —— 数据源单行配置（开关 + Token）
- `release_notes` —— 更新日志；`feedback` —— 问题反馈

## 数据源说明

- **AkShare**（默认，开源免费）：`AkShareFetcher` 东财优先、失败自动回退腾讯；取前复权（qfq）日线。
- **Tushare Pro**（可选）：开关开启后走 `TushareFetcher`，行情写入独立表 `raw_price_daily_tushare`，与 AkShare 物理隔离、可分源比对。Token 优先级：数据库（UI 设置）→ 环境变量 `TUSHARE_TOKEN`。长区间自动分段拉取 + 节流 + 重试。
- 标的代码约定 6 位（如 `510880`）。回测 / 看板在缺数据时自动补拉（先查本地表 → 仅补缺失区间 → UPSERT 幂等），避免重复拉取。

## API 概览

所有接口返回统一格式 `{ code, message, data }`（`code:0` 成功）。

| 领域 | 方法 | 路径 | 说明 |
|------|------|------|------|
| 基础 | GET | `/api/health` | 健康检查 |
| 行情 | POST | `/api/data/fetch` | 手动拉取标的行情（随数据源开关） |
| 标的 | GET | `/api/symbols/search?q=` | 代码 / 名称搜索 |
| 定投 | POST/GET | `/api/backtest/dca` `…/preview` `…/{task_id}/{chart,summary}` | 定投回测（普通 / 智能） |
| MA120 | POST/GET | `/api/backtest/ma120` `…/preview` `…/{task_id}/{chart,summary}` | MA120 策略回测 |
| 网格 | POST/GET | `/api/backtest/grid` `…/preview` `…/{task_id}/{chart,summary}` | 网格交易策略回测 |
| 组合 | POST/GET | `/api/backtest/portfolio` `…/{task_id}/{chart,summary}` | 组合回测（含有效前沿） |
| 最近 | GET | `/api/backtest/recent?limit=` | 合并各策略最近记录 |
| 策略擂台 | GET | `/api/arena/compare` | 多策略 / 多标的横向对比 |
| 市场 | GET | `/api/market/overview?extra=` | 指数概览（随开关） |
| 回撤看板 | GET/POST | `/api/drawboard/{series,backtest,save}/{task_id}/…` | 回撤序列 + 金字塔策略 + 落库 |
| 估值 | GET | `/api/valuation/{indices,single,overlay}` | 估值看板 v2：指数列表 / 单指数通道 / 多指数叠加（旧 `/api/valuation?symbol=` 保留） |
| ETF 流向 | GET | `/api/etf-flow?symbol=` | 份额变动 + 北向（Tushare） |
| 事件看板 | GET/POST | `/api/event/{themes,smart-match,,{id},impact}` | 事件冲击产业链 + LLM 智能匹配 |
| 数据源 | GET/PUT/DELETE | `/api/datasource/{status,token,toggle}` | Tushare 开关 + Token 管理 |
| 更新日志 | GET | `/api/release-notes` | 最新 5 条 |
| Roadmap | GET | `/api/roadmap` | 未实现任务（TASKS.md ☐） |
| 反馈 | GET/POST/DELETE | `/api/feedback` | 问题反馈 |
| MCP 状态 | GET | `/api/mcp/status` | MCP server 连接状态（前端状态面板，expose=false 不回环给 MCP） |

> **MCP Server**（`mcp_server/`，独立容器 `:8020`）：把上表只读查询 + 回测创建类接口包装成 32 个 MCP tool，供 LLM 调用。配置与用法见 [`mcp_server/README.md`](mcp_server/README.md)；接口暴露清单与治理见 [`docs/api-registry.yaml`](docs/api-registry.yaml)。

### 运维 CLI

```bash
# 更新日志管理（免 SQL）
docker exec portlab-backend .venv/bin/python -m app.cli.release_notes \
  add --title "标题" --type feature --released-at 2026-07-18 --detail "详情"
docker exec portlab-backend .venv/bin/python -m app.cli.release_notes list
```

详细参数见 Swagger 文档 `/docs`。

## 项目结构

```
portlab/
├── docker-compose.yml
├── .env.example
├── TASKS.md                      # 任务索引（☑/☐，roadmap 数据源）
├── docs/
│   ├── tasks/                   # 任务拆解文档 001–026 + 验收待确认
│   └── api-registry.yaml        # 接口契约单一事实源（MCP 暴露治理）
├── mcp_server/                   # MCP Server（独立容器）：fastmcp + httpx，32 tool + chart 降采样
│   └── src/portlab_mcp/          # server / client / transforms / registry_loader / tools/
├── mysql/{init,migrations}/      # 建表 / 升级 SQL
├── backend/app/
│   ├── main.py                   # FastAPI 入口（路由注册 + 启动自愈建表）
│   ├── api/                      # 路由：data/backtest(dca/ma120/grid/portfolio)/drawboard/
│   │                             #       arena/market/valuation/etf_flow/event/datasource/
│   │                             #       release_note/recent/roadmap/feedback/symbols/health
│   ├── cli/release_notes.py      # 更新日志管理 CLI
│   ├── models/                   # raw / raw_tushare / valuation / portfolio / grid / event / ...
│   ├── schemas/                  # 各领域响应模型（统一 ApiResponse）
│   └── services/
│       ├── fetcher/              # DataFetcher 抽象 + AkShare/Tushare + valuation_fetcher + registry
│       ├── compute/              # dca / ma120 / grid / portfolio / event_impact 计算引擎 + common
│       ├── drawboard / market / valuation_data / etf_flow / event / arena / roadmap / price_data / storage
└── frontend/src/
    ├── App.vue                   # 导航（品牌区 + 10 功能页 + 数据源/更新日志/GitHub/主题）
    ├── views/                    # Home / Backtest / Ma120Backtest / DrawboardView / GridBacktestView /
    │                             # PortfolioBacktestView / ArenaView / EtfFlowView / ValuationView / EventDashboardView
    ├── components/               # MetricCard / DcaChart / Ma120Chart / *Chart / DataSourceWidget / ReleaseNotesWidget ...
    ├── api/                      # axios 封装 + 全部接口客户端
    └── router/
```

## 任务进度

任务索引见 `TASKS.md`，详情见 `docs/tasks/`。当前 001–020、022–026 已完成（025 修复 POST 创建控制流 bug，026 新增 MCP Server）；**021（股息率 / DCF 估值回测）待实现**（依赖估值看板补出股息率历史序列，本期 csindex 仅当日快照）。
