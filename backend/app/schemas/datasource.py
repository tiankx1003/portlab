"""数据源配置相关 schema（Tushare 开关 + Token 管理）。"""

from pydantic import BaseModel, Field


class TokenUpdate(BaseModel):
    token: str = Field(..., min_length=1, max_length=128, description="Tushare Pro Token")


class ToggleUpdate(BaseModel):
    enabled: bool = Field(..., description="true=启用 Tushare，false=回退 AkShare 免费数据")


class DataSourceStatus(BaseModel):
    tushare_enabled: bool  # 开关状态（true=启用 Tushare，false=用 AkShare）
    active_source: str  # 解析后的生效源：'tushare' / 'akshare'，供前端显示
    tushare_token_masked: str  # 如 ••••abcd，未配置则为 ""
    tushare_configured: bool  # token 是否非空
