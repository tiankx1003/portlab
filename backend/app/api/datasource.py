"""数据源配置接口（Tushare 开关 + Token 管理）。

路由前缀 ``/api/datasource``：
- GET  /status  —— 开关状态、Token 掩码、生效源
- PUT  /token   —— 设置 / 更新 Tushare Token（明文入 DB，持久化）
- DELETE /token —— 清空 Token（不清开关状态）
- PUT  /toggle  —— 开关 Tushare；enabled=true 时校验 Token 非空

业务规则：Token 与开关均落库持久化，重启不丢；Token 写入不立即拉取，
实际拉取发生在回测或手动 fetch 时（避免无谓请求 / 触发限频）。
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.data_source_config import DataSourceConfig
from ..schemas.common import ApiResponse
from ..schemas.datasource import DataSourceStatus, ToggleUpdate, TokenUpdate

router = APIRouter()

_CONFIG_ID = 1


def _mask_token(token: str | None) -> str:
    """Token 掩码：仅显示后 4 位，避免整串回传前端。"""
    if not token:
        return ""
    if len(token) <= 4:
        return "••••"
    return "••••••••" + token[-4:]


def _get_config(db: Session) -> DataSourceConfig:
    """读取单行配置；缺失则建默认行（容错，正常由启动钩子保证存在）。"""
    cfg = db.get(DataSourceConfig, _CONFIG_ID)
    if cfg is None:
        cfg = DataSourceConfig(id=_CONFIG_ID, tushare_enabled=False, tushare_token=None)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _status_data(db: Session) -> DataSourceStatus:
    cfg = _get_config(db)
    configured = bool(cfg.tushare_token)
    active = "tushare" if (cfg.tushare_enabled and configured) else "akshare"
    return DataSourceStatus(
        tushare_enabled=bool(cfg.tushare_enabled),
        active_source=active,
        tushare_token_masked=_mask_token(cfg.tushare_token),
        tushare_configured=configured,
    )


@router.get("/status", response_model=ApiResponse)
def get_status(db: Session = Depends(get_db)) -> ApiResponse:
    return ApiResponse.ok(data=_status_data(db))


@router.put("/token", response_model=ApiResponse)
def update_token(body: TokenUpdate, db: Session = Depends(get_db)) -> ApiResponse:
    cfg = _get_config(db)
    cfg.tushare_token = body.token.strip()
    db.commit()
    return ApiResponse.ok(data=_status_data(db))


@router.delete("/token", response_model=ApiResponse)
def clear_token(db: Session = Depends(get_db)) -> ApiResponse:
    cfg = _get_config(db)
    cfg.tushare_token = None
    db.commit()
    return ApiResponse.ok(data=_status_data(db))


@router.put("/toggle", response_model=ApiResponse)
def toggle(body: ToggleUpdate, db: Session = Depends(get_db)) -> ApiResponse:
    cfg = _get_config(db)
    if body.enabled and not cfg.tushare_token:
        # 双重大门：后端同样校验 Token 非空，前端拦截失效时兜底
        return ApiResponse.error(message="启用 Tushare 前请先设置 Token")
    cfg.tushare_enabled = bool(body.enabled)
    db.commit()
    return ApiResponse.ok(data=_status_data(db))
