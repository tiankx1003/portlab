# PortLab — 个人投资分析工具箱

PortLab 是一个本地部署的个人投资分析平台：**定投回测、MA120 红利策略、回撤买入看板、ETF 资金流向、市场概览**，并支持 **AkShare / Tushare 双数据源**一键切换。前后端 + MySQL 全部 Docker Compose 一键启停。

## 功能一览

| 模块 | 说明 |
|------|------|
| **定投回测**（普通 / 智能均线） | 选标的、频率、金额、区间，逐日算市值/成本/盈亏/收益率；智能模式按均线偏离度动态扣款。XIRR 年化 + 最大回撤 + 双轴图表。 |
| **MA120 红利策略** | 价格跌破 MA120 × 阈值金字塔分批买入，站回 MA 上方分批/全部/半仓兑现；支持固定本金 / 每月投入 / 混合三种资金模式。 |
| **回撤买入策略看板** | 拖动「回撤阈值」实时定义买点：回撤达阈值首买、每再多跌 N% 加仓、新高清仓；左轴价格/回撤镜像 + 右轴市值/收益。 |
| **ETF 资金流向** | 份额变动 + 北向资金两路信号（Tushare），观察机构 / 国家队动向。 |
| **市场概览** | 预置指数（沪深300 / 红利ETF / 红利低波）最新价 + 涨跌幅 + 迷你 sparkline，第 4 格可手动输入代码，一键刷新。 |
| **首页门户** | 功能入口卡片、最近回测记录（点击直达结果）、最近更新、Roadmap；品牌区可点击回首页。 |
| **数据源切换** | 右上角钥匙图标：默认 AkShare 免费；开启 Tushare 后行情独立成表、互不污染。Token 持久化、重启不丢。 |
| **更新日志 / 反馈 / GitHub** | 导航栏铃铛看最新迭代、反馈图标提建议、GitHub 外链。 |

> 估值温度计（PE 历史分位）后端已就绪，因运行环境缺 `py_mini_racer` 原生库暂不可用，详见 `docs/tasks/ACCEPTANCE_PENDING.md`。

## 技术栈

| 组件 | 选择 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.x |
| 数据库 | MySQL 8.x |
| 前端 | Vue 3 + Vite + ECharts 5 + Vue Router + Axios |
| 数据源 | AkShare（默认，东财优先 + 腾讯回退）/ Tushare Pro（可选） |
| 包管理 | uv（后端）/ npm（前端） |
| 部署 | Docker Compose 一键启停 |

## 快速启动

```bash
# 1. 准备环境变量（可选，文件内含默认值可直接用）
cp .env.example .env

# 2. 一键构建并启动 mysql + backend + frontend
docker compose up -d --build

# 3. 验证
curl http://localhost:8010/api/health   # {"code":0,"message":"success","data":{"status":"ok"}}
```

启动后访问：

- 前端：http://localhost:5173
- 后端 API / Swagger 文档：http://localhost:8010/docs

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

本地裸跑前后端时，可在 `frontend/vite.config.ts` 中把代理目标改为 `http://127.0.0.1:8010`（或设环境变量 `VITE_BACKEND_TARGET`）。

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
| 定投 | POST/GET | `/api/backtest/dca` `…/{task_id}/{chart,summary}` | 定投回测（普通 / 智能） |
| MA120 | POST/GET | `/api/backtest/ma120` `…/{task_id}/{chart,summary}` | MA120 策略回测 |
| 最近 | GET | `/api/backtest/recent?limit=` | 合并 DCA/MA120 最近记录 |
| 市场 | GET | `/api/market/overview?extra=` | 指数概览（随开关） |
| 回撤看板 | GET | `/api/drawboard/{series,backtest}` | 回撤序列 + 金字塔策略 |
| 估值 | GET | `/api/valuation?symbol=` | 指数 PE 分位（数据源阻塞时降级） |
| ETF 流向 | GET | `/api/etf-flow?symbol=` | 份额变动 + 北向（Tushare） |
| 数据源 | GET/PUT/DELETE | `/api/datasource/{status,token,toggle}` | Tushare 开关 + Token 管理 |
| 更新日志 | GET | `/api/release-notes` | 最新 5 条 |
| Roadmap | GET | `/api/roadmap` | 未实现任务（TASKS.md ☐） |
| 反馈 | GET/POST/DELETE | `/api/feedback` | 问题反馈 |

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
├── docs/tasks/                   # 任务拆解文档 001–017 + 验收待确认
├── mysql/{init,migrations}/      # 建表 / 升级 SQL
├── backend/app/
│   ├── main.py                   # FastAPI 入口（路由注册 + 启动自愈建表）
│   ├── api/                      # 路由：data/backtest/ma120/drawboard/market/
│   │                             #       valuation/etf_flow/datasource/release_note/
│   │                             #       recent/roadmap/feedback/symbols/health
│   ├── cli/release_notes.py      # 更新日志管理 CLI
│   ├── models/                   # raw / raw_tushare / data_source_config / release_note / ...
│   ├── schemas/                  # 各领域响应模型（统一 ApiResponse）
│   └── services/
│       ├── fetcher/              # DataFetcher 抽象 + AkShare/Tushare + registry(源路由)
│       ├── compute/              # dca / ma120 计算引擎 + common
│       ├── drawboard / market / valuation / etf_flow / roadmap / benchmark / price_data / storage
└── frontend/src/
    ├── App.vue                   # 导航（品牌区 + 功能页 + 数据源/更新日志/GitHub/主题）
    ├── views/                    # Home / Backtest / Ma120Backtest / DrawboardView / EtfFlowView
    ├── components/               # MetricCard / DcaChart / Ma120Chart / DataSourceWidget / ReleaseNotesWidget ...
    ├── api/                      # axios 封装 + 全部接口客户端
    └── router/
```

## 任务进度

任务索引见 `TASKS.md`，详情见 `docs/tasks/`。当前 001–015、017 已完成；016（估值温度计）待 PE 数据源修复。
