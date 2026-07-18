"""数据源路由：源 → 行情表 ORM 模型映射 + 生效源解析。

「数据单独成表」与「避免重复拉取」的交汇点：
拉取前用它定位目标表查本地，拉取后用它定位目标表 UPSERT。
开关关闭（tushare_enabled=0）时 ``resolve_source`` 恒返回 ``'akshare'``，
原有免费链路零感知。
"""

from sqlalchemy.orm import Session

from ...models.raw import RawPriceDaily
from ...models.raw_tushare import RawPriceDailyTushare

# 源 → 行情表 ORM 模型
SOURCE_TABLE = {
    "akshare": RawPriceDaily,
    "tushare": RawPriceDailyTushare,
}


def resolve_source(db: Session) -> str:
    """解析生效数据源：读 ``data_source_config``；

    ``tushare_enabled=1`` 且 token 非空 → ``'tushare'``，否则 ``'akshare'``。
    读取异常（表不存在等）时安全回退 ``'akshare'``，保证默认免费链路可用。
    """
    from ...models.data_source_config import DataSourceConfig

    try:
        cfg = db.get(DataSourceConfig, 1)
    except Exception:  # noqa: BLE001 - 任何读取异常都回退到 AkShare
        return "akshare"
    if cfg is None:
        return "akshare"
    if cfg.tushare_enabled and cfg.tushare_token:
        return "tushare"
    return "akshare"


def source_from_task_id(task_id: str) -> str:
    """从 task_id 反推数据源（带 ``_tushare`` 后缀 → ``'tushare'``，否则 ``'akshare'``）。

    GET chart/summary 等按 task_id 读取的接口据此选择对应行情表，
    使「开启 Tushare 跑出的结果」始终从 Tushare 表读行情（基准 / markPoint）。
    """
    return "tushare" if task_id.endswith("_tushare") else "akshare"
