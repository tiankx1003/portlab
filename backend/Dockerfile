FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

# akshare/numpy 运行期需要的少量系统库
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv（使用已缓存的 latest 镜像，避免联网拉取固定 tag）
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 先拷依赖清单以利用 Docker 层缓存
COPY pyproject.toml ./
RUN uv sync --no-dev

# 再拷源码
COPY . .

EXPOSE 8010

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
