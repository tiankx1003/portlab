"""运行配置：从环境变量读 PortLab API 基址、监听端口、契约表路径。

变量名与 docker-compose 注入对齐（不统一加前缀）：
  - PORTLAB_API_BASE           backend 基址（跨服务共享，无 MCP_ 前缀）
  - MCP_HOST / MCP_HTTP_PORT   监听
  - MCP_REGISTRY_PATH          契约表路径
  - MCP_CHART_TARGET_POINTS    降采样目标点数
本地裸跑可写 .env 或直接 export。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 不设 env_prefix：字段名（大写）即环境变量名，使 PORTLAB_API_BASE 与 MCP_* 共存。
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    portlab_api_base: str = "http://localhost:8010/api"
    mcp_host: str = "0.0.0.0"
    mcp_http_port: int = 8020
    mcp_registry_path: str = "/app/api-registry.yaml"
    mcp_chart_target_points: int = 80


settings = Settings()
