"""配置管理 —— 从环境变量读取。"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # MySQL 连接
    db_host: str = "127.0.0.1"
    db_port: int = 3306
    db_user: str = "portlab"
    db_pass: str = "portlabpass"
    db_name: str = "portlab"

    # 数据拉取数据源
    data_source: str = "akshare"

    # Tushare Pro Token（环境变量兜底；优先级低于数据库 data_source_config.tushare_token）
    tushare_token: str = ""

    # LLM 连接（事件看板智能匹配用；环境变量兜底，优先级低于数据库 llm_config）
    llm_api_base: str = ""
    llm_api_key: str = ""
    llm_model: str = ""

    # MCP server（026）：mcp_url 为容器内探测地址（compose 注入 http://mcp:8020/mcp）；
    # mcp_url_public 为前端展示 / ZCode 配置用的宿主机地址（默认 localhost:8020）。
    mcp_url: str = "http://mcp:8020/mcp"
    mcp_url_public: str = "http://localhost:8020/mcp"


settings = Settings()
