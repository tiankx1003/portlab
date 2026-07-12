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


settings = Settings()
