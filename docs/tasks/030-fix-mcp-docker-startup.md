# 030 — 修复 mcp 容器在 Docker Desktop 启动失败

## 目标

修复 mcp 容器两个一直存在、被「首次启动即挂载失败」掩盖的启动 bug，使其在
Docker Desktop（macOS VirtioFS）下能正常启动。

## Bug 根因与修复

### ① 嵌套 bind mount 冲突

`./mcp_server:/app` 已占用 `/app`，再 `./docs/api-registry.yaml:/app/api-registry.yaml:ro`
单文件挂载，VirtioFS 报 `mountpoint ... is outside of rootfs`（不支持在已 bind mount
的目录内再单文件 bind mount）。

**修复**：`docker-compose.yml` mcp 段改 `./docs:/docs:ro` 整目录挂载 +
`MCP_REGISTRY_PATH=/docs/api-registry.yaml`。

### ② PYTHONPATH 缺失

mcp_server 是 src 布局（`src/portlab_mcp/`），Dockerfile 漏设 `PYTHONPATH`，
`python -m portlab_mcp.server` 报 `No module named 'portlab_mcp'`。

**修复**：Dockerfile ENV 段补 `PYTHONPATH=/app/src`。

## 验收

- [x] mcp 容器正常 Up，不再 restart 循环
- [x] `/healthz` 返回 `status=ok, tool_count=32, backend_reachable=true, drift_warnings=[]`
- [x] 契约表挂载到 `/docs` 解析成功（drift_warnings 为空）
