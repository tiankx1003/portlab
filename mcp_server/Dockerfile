FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# fastmcp 依赖 httpx/pydantic，运行期无需额外系统库；仅装 ca-certificates 保证 HTTPS。
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（用已缓存的 latest 镜像，避免联网拉固定 tag）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先拷依赖清单以利用 Docker 层缓存（与 backend 同款手法）
COPY pyproject.toml ./
RUN uv sync --no-dev

# 再拷源码
COPY src/ ./src/

# 契约表由 compose 以只读卷挂载到 /app/api-registry.yaml，改 YAML 重启即生效，无需重 build。
EXPOSE 8020

CMD [".venv/bin/python", "-m", "portlab_mcp.server"]
