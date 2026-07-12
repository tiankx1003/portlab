# PortLab — 个人投资分析工具箱

PortLab 是一个个人投资分析平台，提供**定投（DCA）回测**、收益追踪等功能，持续集成更多分析能力。

当前版本 **v0.1.0**：定投回测 MVP —— 选择标的、设定投频率与金额，回测整个定投区间的市值变化，以双轴图表展示结果。

## 技术栈

| 组件 | 选择 |
|------|------|
| 后端 | Python 3.12 + FastAPI + SQLAlchemy 2.x |
| 数据库 | MySQL 8.x |
| 前端 | Vue 3 + Vite + ECharts 5 + Vue Router + Axios |
| 数据源 | AkShare（A 股日线行情） |
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

> **首次拉取基础镜像提示**：若 `docker compose up` 因拉不到 `mysql` / `python` / `node` 镜像失败（Docker Hub 不可达），可经国内镜像源拉取并重打 tag，例如：
> ```bash
> docker pull docker.m.daocloud.io/library/mysql:8.4 && docker tag docker.m.daocloud.io/library/mysql:8.4 mysql:8.4
> # 同理处理 python:3.12-slim、node:20-alpine
> ```
> 随后再次执行 `docker compose up -d --build`。

## 功能：定投回测

1. 在「定投回测」页输入标的代码（支持搜索 A 股）、定投频率（每周/每月）、投资日、每期金额、日期区间。
2. 点击「开始回测」—— 系统自动补齐缺失行情、逐日计算市值/成本/盈亏/收益率。
3. 结果以**双轴组合图**展示：左轴金额（市值线 + 成本虚线 + 盈亏柱），右轴收益率曲线；上方为汇总指标卡片。

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

首次启动由 `mysql/init/01_schema.sql` 自动建库建表。表命名约定：

- `raw_*` —— 原始拉取数据（`raw_price_daily`）
- `calc_*` —— 计算中间结果（`calc_dca_backtest`）
- `result_*` —— 最终输出（`result_dca_summary`）

## 项目结构

```
portlab/
├── docker-compose.yml
├── .env.example
├── SPEC.md                 # 产品规格
├── docs/tasks/             # 任务拆解
├── mysql/init/01_schema.sql
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── app/
│       ├── main.py         # FastAPI 入口（CORS、统一异常处理、路由）
│       ├── config.py       # 环境变量配置
│       ├── database.py     # SQLAlchemy engine/session
│       ├── api/            # health / data / backtest / symbols 路由
│       ├── models/         # raw / calc / result 模型
│       ├── schemas/        # ApiResponse（统一响应）+ backtest
│       └── services/
│           ├── fetcher/    # DataFetcher 抽象 + AkShareFetcher
│           ├── compute/    # dca.py 定投回测计算引擎
│           └── storage.py  # 行情 UPSERT
└── frontend/
    ├── package.json
    ├── vite.config.ts      # /api 代理
    ├── Dockerfile
    └── src/
        ├── api/            # axios 封装 + 接口
        ├── components/     # MetricCard / DcaChart
        ├── views/          # Home / Backtest
        └── router/
```

## 数据源说明

- 行情数据通过 **AkShare** 获取（开源免费，覆盖 A 股）。
- `AkShareFetcher` 采用**东财优先、失败自动回退腾讯**策略，提升稳定性；取前复权（qfq）日线。
- 标的代码约定为 6 位（如 `000001` 平安银行）。回测创建时若库中无对应区间行情，会自动拉取。
- 标的搜索基于 AkShare 的 A 股代码/名称列表（指数、基金暂不支持，可在表单中直接输入代码）。

## API 概览

所有接口返回统一格式 `{ code, message, data }`（`code:0` 成功）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 健康检查 |
| POST | `/api/data/fetch` | 手动拉取标的行情 |
| GET | `/api/symbols/search?q=` | 标的代码/名称搜索 |
| POST | `/api/backtest/dca` | 创建定投回测，返回 `task_id` |
| GET | `/api/backtest/dca/{task_id}/chart` | 回测逐日图表数据（ECharts 友好） |
| GET | `/api/backtest/dca/{task_id}/summary` | 回测汇总指标 |

详细参数见 Swagger 文档 `/docs`。
