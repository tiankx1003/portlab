"""FastAPI 入口。"""

import importlib.util
import logging
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .api import (
    backtest,
    data,
    datasource,
    drawboard,
    etf_flow,
    event_dashboard,
    feedback,
    grid,
    health,
    ma120,
    market,
    portfolio,
    recent,
    release_note,
    roadmap,
    symbols,
    valuation,
)
from .schemas.common import ApiResponse
from .services import symbol_catalog

logger = logging.getLogger(__name__)


def _ensure_data_source_config() -> None:
    """启动时确保新增表与初始数据就绪（自愈，不影响 AkShare 默认链路）。

    - 按 CREATE TABLE IF NOT EXISTS 语义创建 ``raw_price_daily_tushare``、
      ``data_source_config``、``release_notes``（幂等，不触碰其他表；
      覆盖未手动执行 SQL 的裸机开发场景）。
    - ``data_source_config`` 确保 ``id=1`` 默认行（开关关闭、Token 空），已存在不覆盖。
    - ``release_notes`` 为空时预置最近迭代种子（fresh 安装由 init/04 提供；
      此处兜底已部署库未跑 init 的情况）。
    """
    try:
        from .database import Base, SessionLocal, engine
        from .models.data_source_config import DataSourceConfig
        from .models.raw_tushare import RawPriceDailyTushare
        from .models.release_note import ReleaseNote

        Base.metadata.create_all(
            engine,
            tables=[
                DataSourceConfig.__table__,
                RawPriceDailyTushare.__table__,
                ReleaseNote.__table__,
            ],
        )
        with SessionLocal() as db:
            db.execute(
                text(
                    "INSERT INTO data_source_config (id, tushare_enabled, tushare_token) "
                    "VALUES (1, 0, NULL) "
                    "ON DUPLICATE KEY UPDATE id = id"
                )
            )
            _seed_release_notes_if_empty(db)
            db.commit()
    except Exception as e:  # noqa: BLE001 - 自愈失败不阻断启动，AkShare 链路仍可用
        logger.warning("启动自愈（数据源/更新日志表）失败（不影响 AkShare 默认链路）: %s", e)


def _seed_release_notes_if_empty(db) -> None:
    """release_notes 为空时预置最近迭代种子（幂等：title+released_at 唯一）。"""
    from sqlalchemy import func, select

    from .models.release_note import ReleaseNote

    cnt = db.execute(select(func.count()).select_from(ReleaseNote)).scalar() or 0
    if cnt > 0:
        return
    db.execute(
        text(
            "INSERT INTO release_notes (title, type, detail, released_at, "
            "is_deleted, created_at) VALUES "
            "('事件冲击产业链看板', 'feature', "
            "'事件→标的池→产业链关系图 + 波动对比 + 相关性热力图；"
            "LLM 智能匹配（OpenAI 兼容协议）', "
            "'2026-07-19', 0, UTC_TIMESTAMP()), "
            "('估值温度计 / 估值分位看板', 'feature', "
            "'指数 PE 历史分位 + 温度计仪表，回答「现在贵不贵」"
            "（沪深300/中证500/中证1000/上证50/创业板指）', "
            "'2026-07-18', 0, UTC_TIMESTAMP()), "
            "('回测直达 / 更新日志 CLI / Tushare 限频治理', 'improvement', "
            "'?task= 直达已有回测结果；release_notes CLI 免 SQL 维护；"
            "Tushare 分段拉取+节流+重试', "
            "'2026-07-18', 0, UTC_TIMESTAMP()), "
            "('ETF 资金流向看板', 'feature', "
            "'份额变动 + 北向资金(Tushare)，观察机构/国家队动向', "
            "'2026-07-18', 0, UTC_TIMESTAMP()), "
            "('回撤买入策略看板', 'feature', "
            "'拖动回撤阈值实时定义买点，金字塔分批买入、新高清仓', "
            "'2026-07-18', 0, UTC_TIMESTAMP()), "
            "('更新日志 + GitHub 仓库入口', 'feature', "
            "'导航栏铃铛展示最新 5 条变更；GitHub 外链图标', "
            "'2026-07-18', 0, UTC_TIMESTAMP()), "
            "('首页改版为工具箱门户', 'feature', "
            "'市场概览/最近回测/最近更新/Roadmap；品牌区可点击回首页', "
            "'2026-07-18', 0, UTC_TIMESTAMP()), "
            "('Tushare 数据源扩展', 'feature', "
            "'右上角钥匙图标开关 Tushare 数据源；Token 持久化、行情独立成表、避免重复拉取', "
            "'2026-07-17', 0, UTC_TIMESTAMP()), "
            "('MA120 新增止盈步长参数', 'feature', "
            "'batch 卖出方式下可配置止盈步长，灵活控制分批卖出节奏', "
            "'2026-07-16', 0, UTC_TIMESTAMP()), "
            "('问题反馈功能上线', 'feature', "
            "'右上角反馈图标，支持 Markdown 提交，反馈保留 3 天', "
            "'2026-07-16', 0, UTC_TIMESTAMP()), "
            "('图表图例提示与卡片交互优化', 'improvement', "
            "'图例新增提示图标；MA120 卡片/表单交互打磨', "
            "'2026-07-16', 0, UTC_TIMESTAMP()), "
            "('红利 MA120 策略回测全链路', 'feature', "
            "'新增 MA120 策略回测（计算引擎 + API + 前端）', "
            "'2026-07-15', 0, UTC_TIMESTAMP()), "
            "('自定义品牌图标', 'improvement', "
            "'favicon 与左上角 Logo 自定义', "
            "'2026-07-12', 0, UTC_TIMESTAMP()) "
            "ON DUPLICATE KEY UPDATE title = VALUES(title)"
        )
    )


def _ensure_py_mini_racer_lib() -> None:
    """老版 py_mini_racer 在 aarch64 把原生库存成 ``armlibmini_racer.glibc.so``，
    但加载器找 ``libmini_racer.glibc.so`` → 补软链修复（乐咕乐股 PE 接口依赖）。"""
    try:
        spec = importlib.util.find_spec("py_mini_racer")
        if not spec or not spec.submodule_search_locations:
            return
        d = Path(spec.submodule_search_locations[0])
        arm = d / "armlibmini_racer.glibc.so"
        target = d / "libmini_racer.glibc.so"
        if arm.exists() and not target.exists():
            target.symlink_to("armlibmini_racer.glibc.so")
            logger.info("py_mini_racer: 补软链 libmini_racer.glibc.so")
    except Exception as e:  # noqa: BLE001
        logger.warning("py_mini_racer 软链自愈失败（估值接口将降级）: %s", e)


def _ensure_event_tables() -> None:
    """启动自愈：事件冲击产业链看板（018）五张表 + llm_config 默认行 + 内置主题。

    - CREATE TABLE IF NOT EXISTS 语义建表（幂等；覆盖未手动执行 init/08 或 migrations/009 的场景）。
    - ``llm_config`` 确保 ``id=1`` 默认行（enabled=0），已存在不覆盖。
    - 内置主题（id 1~3）+ 成分股样例空表时预置（fresh 由 init/08 提供；此处兜底已部署库）。
    - 若 ``.env`` 配置了 LLM 三项而 DB 行为空，seed 进 DB 并启用（headless 即时生效）。
    """
    try:
        from .database import Base, SessionLocal, engine
        from .models.event import Event
        from .models.llm_config import LlmConfig
        from .models.theme import EventStock, Theme, ThemeStock
        from .services.matcher import bootstrap_llm_config_from_env

        Base.metadata.create_all(
            engine,
            tables=[
                Event.__table__,
                Theme.__table__,
                ThemeStock.__table__,
                EventStock.__table__,
                LlmConfig.__table__,
            ],
        )
        with SessionLocal() as db:
            db.execute(
                text(
                    "INSERT INTO llm_config (id, api_base, api_key, model, enabled) "
                    "VALUES (1, NULL, NULL, NULL, 0) "
                    "ON DUPLICATE KEY UPDATE id = id"
                )
            )
            _seed_builtin_themes(db)
            db.commit()
            bootstrap_llm_config_from_env(db)
    except Exception as e:  # noqa: BLE001 - 自愈失败不阻断启动
        logger.warning("启动自愈（事件看板表）失败: %s", e)


def _ensure_drawboard_tables() -> None:
    """启动自愈：回撤买入策略看板（019）两张表（calc_drawboard_backtest + result_drawboard_summary）。

    - CREATE TABLE IF NOT EXISTS 语义建表（幂等；覆盖未手动执行 init/09 或 migrations/010 的场景）。
    - 与 MA120/DCA 不同，这里补自愈以兜底裸机开发；fresh 安装由 init/09 提供同两表。
    """
    try:
        from .database import Base, engine
        from .models.drawboard import CalcDrawboardBacktest, ResultDrawboardSummary

        Base.metadata.create_all(
            engine,
            tables=[
                CalcDrawboardBacktest.__table__,
                ResultDrawboardSummary.__table__,
            ],
        )
    except Exception as e:  # noqa: BLE001 - 自愈失败不阻断启动
        logger.warning("启动自愈（回撤看板表）失败: %s", e)


def _ensure_grid_tables() -> None:
    """启动自愈：网格交易策略回测（020）两张表（calc_grid_backtest + result_grid_summary）。

    CREATE TABLE IF NOT EXISTS 建表（幂等）；覆盖未跑 init/10 或 migrations/011 的裸机场景。
    """
    try:
        from .database import Base, engine
        from .models.grid import CalcGridBacktest, ResultGridSummary

        Base.metadata.create_all(
            engine,
            tables=[
                CalcGridBacktest.__table__,
                ResultGridSummary.__table__,
            ],
        )
    except Exception as e:  # noqa: BLE001 - 自愈失败不阻断启动
        logger.warning("启动自愈（网格回测表）失败: %s", e)


def _ensure_portfolio_tables() -> None:
    """启动自愈：组合回测（022）两张表（calc_portfolio_nav + result_portfolio_summary）。"""
    try:
        from .database import Base, engine
        from .models.portfolio import CalcPortfolioNav, ResultPortfolioSummary

        Base.metadata.create_all(
            engine,
            tables=[
                CalcPortfolioNav.__table__,
                ResultPortfolioSummary.__table__,
            ],
        )
    except Exception as e:  # noqa: BLE001 - 自愈失败不阻断启动
        logger.warning("启动自愈（组合回测表）失败: %s", e)


def _seed_builtin_themes(db) -> None:
    """内置主题（id 1~3）+ 成分股样例空表时预置（幂等）。与 init/08 同源。"""
    from sqlalchemy import func, select

    from .models.theme import Theme

    cnt = db.execute(select(func.count()).select_from(Theme)).scalar() or 0
    if cnt > 0:
        return
    db.execute(
        text(
            "INSERT INTO theme (id, name, keywords, is_builtin) VALUES "
            "(1, '新茶饮产业链', '新茶饮,奶茶,花茶,茶饮,茉莉花,茶叶', 1), "
            "(2, '香料产业链',   '香料,香精,食用香精,提取,茉莉,花香', 1), "
            "(3, '农业种植',     '农业,种植,种子,农产品,花卉,经济作物', 1) "
            "ON DUPLICATE KEY UPDATE id = id"
        )
    )
    db.execute(
        text(
            "INSERT IGNORE INTO theme_stock (theme_id, symbol, chain_role, weight) VALUES "
            "(1,'600598','upstream',1.00),(1,'000998','upstream',0.80),"
            "(1,'002568','midstream',1.00),(1,'600872','midstream',0.70),"
            "(1,'603288','downstream',1.00),(1,'603027','downstream',0.60),"
            "(2,'600251','upstream',1.00),(2,'600598','upstream',0.70),"
            "(2,'002568','midstream',1.00),(2,'600872','midstream',0.70),"
            "(2,'603288','downstream',0.80),(2,'600887','downstream',0.50),"
            "(3,'000998','upstream',1.00),(3,'600598','upstream',1.00),"
            "(3,'600108','upstream',0.70),(3,'000061','midstream',1.00),"
            "(3,'600887','downstream',0.80),(3,'603288','downstream',0.60)"
        )
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _ensure_py_mini_racer_lib()
    _ensure_data_source_config()
    _ensure_event_tables()
    _ensure_drawboard_tables()
    _ensure_grid_tables()
    _ensure_portfolio_tables()
    # 启动时后台预热 A 股标的目录，使名称解析（图表标题）稳定可用
    threading.Thread(target=symbol_catalog.warmup, daemon=True).start()
    yield


app = FastAPI(title="PortLab", version="0.1.0", lifespan=lifespan)

# 开发期允许前端（5173）跨域访问；同时 vite 已做 /api 代理
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """参数校验失败也统一为 ApiResponse 格式（HTTP 200，code:1）。"""
    parts: list[str] = []
    for err in exc.errors():
        field = ".".join(str(x) for x in err["loc"] if x not in ("body", "query", "path"))
        msg = err["msg"].removeprefix("Value error, ") if err["msg"].startswith("Value error, ") else err["msg"]
        parts.append(f"{field}: {msg}" if field else msg)
    message = "; ".join(parts) or "参数校验失败"
    return JSONResponse(status_code=200, content=ApiResponse.error(message=message).model_dump())


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(data.router, prefix="/api/data", tags=["data"])
app.include_router(backtest.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(ma120.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(grid.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(portfolio.router, prefix="/api/backtest", tags=["backtest"])
app.include_router(recent.router, prefix="/api/backtest", tags=["backtest"])  # /api/backtest/recent
app.include_router(symbols.router, prefix="/api/symbols", tags=["symbols"])
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
app.include_router(datasource.router, prefix="/api/datasource", tags=["datasource"])
app.include_router(release_note.router, prefix="/api/release-notes", tags=["release-notes"])
app.include_router(market.router, prefix="/api/market", tags=["market"])  # /api/market/overview
app.include_router(roadmap.router, prefix="/api/roadmap", tags=["roadmap"])  # /api/roadmap
app.include_router(drawboard.router, prefix="/api/drawboard", tags=["drawboard"])
app.include_router(valuation.router, prefix="/api/valuation", tags=["valuation"])  # /api/valuation
app.include_router(etf_flow.router, prefix="/api/etf-flow", tags=["etf-flow"])  # /api/etf-flow
app.include_router(event_dashboard.router, prefix="/api/event", tags=["event"])  # /api/event
