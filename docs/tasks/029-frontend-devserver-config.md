# 029 — 前端 dev server 配置化（端口 / 代理目标 / host 白名单）

## 目标

把前端 Vite dev server 的端口、后端代理目标、host 白名单从硬编码改为环境变量驱动，
并修复 `VITE_BACKEND_TARGET` 此前「.env 写了但 frontend 容器无 `environment:` 段、
靠默认值恰好等于容器内地址而碰巧能用」的隐患。

## 改动

新增三个环境变量（`.env` / `.env.example` 统一管理，docker-compose frontend 段透传）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `VITE_PORT` | 5173 | dev server 端口，容器内外一致（compose 端口映射内外都用它） |
| `VITE_BACKEND_TARGET` | `http://backend:8010` | /api 代理目标；裸跑改 `http://127.0.0.1:8010` |
| `VITE_ALLOWED_HOSTS` | （空） | Vite host 白名单（绕过 DNS rebinding 防护），逗号分隔；留空仅 localhost |

涉及文件：

- `frontend/vite.config.ts`：三变量从 `process.env` 读；`allowedHosts` 解析逗号分隔数组，空时不设该键
- `frontend/Dockerfile`：CMD 改 `sh -c` 动态读 `VITE_PORT`（原硬编码 `--port 5173` 会覆盖 config）
- `docker-compose.yml`：frontend 段加 `environment:` 透传三变量 + 端口映射 `${VITE_PORT:-5173}:${VITE_PORT:-5173}`
- `.env` / `.env.example`：追加 Frontend 段

## 验收

- [x] `docker compose config` 校验通过，解析出正确的 VITE_* 与端口映射
- [x] 改 `.env` 的 `VITE_PORT` 重启 frontend 容器即生效（实测 5174）
- [x] `VITE_BACKEND_TARGET` 在 docker 下真正透传进容器（不再靠默认值碰巧）
- [x] `VITE_ALLOWED_HOSTS` 留空退回仅 localhost；填值后绕过 host 校验
