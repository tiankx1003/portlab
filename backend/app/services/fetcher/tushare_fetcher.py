"""Tushare Pro 数据源实现。

取**前复权(qfq)**日线 OHLCV，与 ``AkShareFetcher`` 语义一致，便于两源数据对照。

symbol 约定：内部统一使用裸代码（如 ``510880``），拉取时按代码首位映射为 Tushare
``ts_code``（如 ``510880.SH``），与 AkShare 的 ``_to_tencent_symbol`` 同源逻辑。

Token 解析优先级（先到先用）：
1. 数据库 ``data_source_config.tushare_token``（UI 设置，运行时可改，**主入口**）
2. 环境变量 ``TUSHARE_TOKEN``（.env / docker-compose，便于 headless 部署）
3. 均无 → 抛 ``FetchError``，提示在右上角钥匙图标中设置
"""

import time
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import pandas as pd

from .base import DataFetcher, FetchError, PriceBar

# Tushare 成交量 ``vol`` 单位为「手」（=100 股），需 × 100 转为「股」，与 AkShare 对齐
_VOL_UNIT = 100

# 限频治理参数（013）
_MAX_DAYS_PER_CALL = 1000  # 单次 pro_bar 覆盖的最大日历天数（日线约 4 年，留足行数余量）
_MIN_INTERVAL = 0.3  # 最小请求间隔（秒），避免连发触发限频
_MAX_RETRIES = 3  # 瞬时错误重试次数
# 视为「积分 / 权限不足」的关键词：命中则不重试，直接抛可读错误
_PERMISSION_KEYWORDS = ("积分", "权限", "permission", "points", "额度", "无权限")

# 进程级最近一次 pro_bar 调用时间戳（节流用）
_last_call_ts: float = 0.0


class TushareFetcher(DataFetcher):
    name = "tushare"

    def fetch_daily(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        token = _resolve_token()
        code = _to_tushare_code(symbol)
        asset = _asset_type(symbol)

        # 延迟导入：tushare 非必装依赖，开关关闭（用 AkShare）时不应影响应用启动
        try:
            import tushare as ts
        except ImportError as e:  # pragma: no cover - 依赖缺失时的友好提示
            raise FetchError(
                "未安装 tushare，请在后端执行 `uv sync` 或 `pip install tushare` 后重试"
            ) from e

        ts.set_token(token)
        ranges = _split_ranges(start_date, end_date, _MAX_DAYS_PER_CALL)
        seen: set[date] = set()
        bars: list[PriceBar] = []
        for s, e in ranges:
            df = _call_pro_bar(ts, code, s, e, asset)
            if df is None:
                continue
            # Tushare 个别错误以 dict 形式返回（含 msg 字段，常为积分 / 权限不足）
            if isinstance(df, dict):
                msg = df.get("msg") or str(df)
                raise FetchError(f"Tushare 接口调用失败：{msg}")
            if df.empty:
                continue
            for b in _df_to_bars(df, symbol):
                if b.trade_date in seen:
                    continue
                seen.add(b.trade_date)
                bars.append(b)
        bars.sort(key=lambda b: b.trade_date)
        return bars


def _resolve_token() -> str:
    """按 §3.1 优先级解析 Tushare Token。"""
    # 1. 数据库（主入口）
    try:
        from ...database import SessionLocal
        from ...models.data_source_config import DataSourceConfig

        with SessionLocal() as db:
            cfg = db.get(DataSourceConfig, 1)
            if cfg and cfg.tushare_token:
                return cfg.tushare_token.strip()
    except Exception:  # noqa: BLE001 - 读 DB 失败时回退到环境变量
        pass

    # 2. 环境变量兜底
    from ...config import settings

    token = (settings.tushare_token or "").strip()
    if token:
        return token

    # 3. 均无
    raise FetchError("未配置 Tushare Token，请在右上角钥匙图标中设置")


def _split_ranges(start: date, end: date, max_days: int) -> list[tuple[date, date]]:
    """将 [start, end] 按最大日历天数切段（避免单次 pro_bar 行数触顶）。"""
    if start > end:
        return []
    if (end - start).days <= max_days:
        return [(start, end)]
    ranges: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        nxt = min(end, cur + timedelta(days=max_days))
        ranges.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return ranges


def _throttle() -> None:
    """进程级最小请求间隔节流，避免连发触发 Tushare 限频。"""
    global _last_call_ts
    now = time.monotonic()
    wait = _MIN_INTERVAL - (now - _last_call_ts)
    if wait > 0:
        time.sleep(wait)
    _last_call_ts = time.monotonic()


def _call_pro_bar(ts, code: str, start: date, end: date, asset: str):
    """带节流 + 瞬时错误重试的 pro_bar 调用；积分/权限不足不重试。"""
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES):
        _throttle()
        try:
            return ts.pro_bar(
                ts_code=code,
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adj="qfq",
                asset=asset,
            )
        except Exception as ex:  # noqa: BLE001
            last_err = ex
            msg = str(ex)
            if any(k in msg for k in _PERMISSION_KEYWORDS):
                raise FetchError(f"Tushare 接口调用失败（可能是积分/权限不足）：{msg}") from ex
            # 限频 / 网络瞬时错误：退避后重试
            time.sleep(0.5 * (attempt + 1))
    raise FetchError(
        f"Tushare 接口调用失败（重试 {_MAX_RETRIES} 次仍失败）：{last_err}"
    ) from last_err


def _to_tushare_code(symbol: str) -> str:
    """裸代码 → Tushare ts_code（带交易所后缀）。与 AkShare 同源逻辑。"""
    s = symbol.strip().upper()
    if "." in s:  # 已带后缀
        return s
    if not s:
        raise FetchError("标的代码为空")
    head = s[0]
    if head in ("6", "5"):  # 沪市主板 / 科创板 / ETF
        return f"{s}.SH"
    if head in ("0", "3", "1"):  # 深市主板 / 创业板 / ETF
        return f"{s}.SZ"
    if head in ("4", "8"):  # 北交所
        return f"{s}.BJ"
    return f"{s}.SZ"  # 兜底按深市处理


def _asset_type(symbol: str) -> str:
    """按代码首位判定资产类型：ETF / 基金 → ``FD``，股票 → ``E``。"""
    head = symbol.strip()[0]
    if head in ("5", "1"):  # 5xxxxx.SH / 1xxxxx.SZ 多为 ETF / 场内基金
        return "FD"
    return "E"


def _df_to_bars(df: pd.DataFrame, symbol: str) -> list[PriceBar]:
    # Tushare 默认按 trade_date 倒序返回，统一升序
    df = df.sort_values("trade_date")
    bars: list[PriceBar] = []
    for _, row in df.iterrows():
        td = datetime.strptime(str(row["trade_date"]), "%Y%m%d").date()
        bars.append(
            PriceBar(
                symbol=symbol,
                trade_date=td,
                open=_to_decimal(row.get("open")),
                close=_to_decimal(row.get("close")),
                high=_to_decimal(row.get("high")),
                low=_to_decimal(row.get("low")),
                volume=_to_int(row.get("vol")),
            )
        )
    return bars


def _to_decimal(v) -> Decimal:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        raise FetchError("价格为空，数据不完整")
    try:
        return Decimal(str(v))
    except (InvalidOperation, ValueError, TypeError) as e:
        raise FetchError(f"价格无法解析为数值: {v!r}") from e


def _to_int(v) -> int | None:
    """Tushare ``vol`` 单位为「手」，统一 × 100 转为「股」；空值返回 None。"""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(round(float(v) * _VOL_UNIT))
    except (ValueError, TypeError):
        return None
