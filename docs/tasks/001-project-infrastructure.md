# 001 — 项目基础设施搭建

## 目标

搭建 PortLab 项目的基础运行环境，确保前后端、数据库可通过 Docker Compose 一键启动。

## 依赖

无（首个任务）

## 交付物

### 1. docker-compose.yml

包含以下服务：

- **mysql**: MySQL 8.x，持久化挂载 `./mysql/data`，端口 3306
- **backend**: Python FastAPI 应用，依赖 mysql，暴露 8010 端口
- **frontend**: Vue 3 + Vite 开发服务器，暴露 5173 端口，通过 proxy 转发 `/api` 到 backend

### 2. backend 骨架

- `pyproject.toml`（uv 管理）：fastapi、uvicorn、sqlalchemy、pymysql、pydantic-settings
- `app/main.py`：FastAPI 入口，注册路由，CORS 配置
- `app/config.py`：从环境变量读取配置（DB_HOST、DB_PORT、DB_USER、DB_PASS、DB_NAME）
- `app/database.py`：SQLAlchemy engine + session
- `Dockerfile`：基于 python:3.12-slim，使用 uv 安装依赖
- 健康检查端点 `GET /api/health` 返回 `{"status": "ok"}`

### 3. frontend 骨架

- `package.json`：vue 3、vue-router、axios、echarts、vite
- `src/App.vue`：基础布局，含导航和 `<router-view />`
- `src/api/`：axios 实例封装，baseURL 指向 `/api`
- `vite.config.ts`：proxy `/api` → `http://backend:8010`
- `Dockerfile`：基于 node:20-alpine

### 4. MySQL 初始化

- `mysql/init/01_schema.sql`：创建数据库 `portlab`
- 建表 `raw_price_daily`（标的行情数据）
- 建表 `calc_dca_backtest`（定投回测逐日计算结果）
- 建表 `result_dca_summary`（定投回测汇总指标）

### 5. 统一 API 响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

定义统一的 `ApiResponse` Pydantic model，所有接口返回此格式。

## 验收标准

- [ ] `docker compose up -d` 可一键启动全部服务，无报错
- [ ] `GET http://localhost:8010/api/health` 返回 `{"code": 0, "message": "success", "data": {"status": "ok"}}`
- [ ] 前端 `http://localhost:5173` 可正常访问
- [ ] MySQL 表结构通过 `DESC` 验证存在
- [ ] `.env.example` 包含所有需要的环境变量
