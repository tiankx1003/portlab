"""事件冲击产业链看板接口（018）。

路由前缀 ``/api/event``：
- GET    /themes            列出主题模板
- GET    /themes/{id}       主题详情含成分股
- GET    /llm-config        LLM 配置状态（key 掩码）
- PUT    /llm-config        设置/更新 LLM 连接（可选 ?test=true 连通性测试）
- POST   /smart-match       智能匹配（LLM 判定相关标的与产业链角色）
- GET    /concept-stocks    实时拉概念板块成分股（补全候选池）
- POST   /                  创建事件（含标的池）
- GET    /{id}              事件详情
- PUT    /{id}/stocks       更新事件标的池
- GET    /{id}/impact       三视图合并数据（?before&after）
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.event import Event
from ..models.llm_config import LlmConfig
from ..models.theme import EventStock, Theme, ThemeStock
from ..schemas.common import ApiResponse
from ..schemas.event_dashboard import (
    ChainGroups,
    EventBrief,
    EventCreate,
    EventImpactData,
    EventStockOut,
    EventStockUpdate,
    LlmConfigStatus,
    LlmConfigUpdate,
    MatchedStock,
    RankingItem,
    SmartMatchRequest,
    SymbolInfo,
    ThemeBrief,
    ThemeDetail,
    ThemeStockItem,
    WindowReturnSeries,
)
from ..services import symbol_catalog
from ..services.compute import event_impact
from ..services.fetcher.base import FetchError
from ..services.fetcher.concept_fetcher import fetch_concept_stocks_em
from ..services.matcher import LlmNotConfiguredError, smart_match, test_llm_connection

router = APIRouter()

_CONFIG_ID = 1
_VALID_ROLES = {"upstream", "midstream", "downstream"}
_BENCHMARK_SYMBOL = "510300"  # 沪深300ETF（可交易，行情按股票拉取；000300 指数代码取不到）
_BENCHMARK_NAME = "沪深300ETF"


# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------
def _mask_key(key: str | None) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "••••"
    return "••••••••" + key[-4:]


def _get_llm_config(db: Session) -> LlmConfig:
    """读取单行配置；缺失则建默认行（容错，正常由启动钩子保证）。"""
    cfg = db.get(LlmConfig, _CONFIG_ID)
    if cfg is None:
        cfg = LlmConfig(id=_CONFIG_ID, enabled=False)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _llm_status(db: Session) -> LlmConfigStatus:
    cfg = _get_llm_config(db)
    api_base = cfg.api_base or ""
    model = cfg.model or ""
    configured = bool(api_base and cfg.api_key and model)
    return LlmConfigStatus(
        enabled=bool(cfg.enabled),
        api_base=api_base,
        api_key_masked=_mask_key(cfg.api_key),
        model=model,
        configured=configured,
    )


def _name_of(symbol: str) -> str:
    return symbol_catalog.lookup_name(symbol) or ""


def _norm_chain(role: str) -> str:
    r = (role or "").strip().lower()
    return r if r in _VALID_ROLES else "midstream"


# ---------------------------------------------------------------------------
# 主题
# ---------------------------------------------------------------------------
@router.get("/themes", response_model=ApiResponse)
def list_themes(db: Session = Depends(get_db)) -> ApiResponse:
    themes = db.execute(select(Theme).order_by(Theme.id)).scalars().all()
    # 一次查询拿全部计数
    counts: dict[int, int] = {}
    if themes:
        rows = db.execute(
            select(ThemeStock.theme_id, func.count())
            .where(ThemeStock.theme_id.in_([t.id for t in themes]))
            .group_by(ThemeStock.theme_id)
        ).all()
        counts = {r[0]: r[1] for r in rows}
    data = [
        ThemeBrief(
            id=t.id,
            name=t.name,
            is_builtin=bool(t.is_builtin),
            keywords=t.keywords,
            stock_count=counts.get(t.id, 0),
        ).model_dump()
        for t in themes
    ]
    return ApiResponse.ok(data=data)


@router.get("/themes/{theme_id}", response_model=ApiResponse)
def get_theme(theme_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    t = db.get(Theme, theme_id)
    if t is None:
        return ApiResponse.error(message="主题不存在")
    rows = (
        db.execute(
            select(ThemeStock).where(ThemeStock.theme_id == theme_id)
        )
        .scalars()
        .all()
    )
    stocks = [
        ThemeStockItem(
            symbol=r.symbol,
            name=_name_of(r.symbol),
            chain_role=r.chain_role,
            weight=float(r.weight),
        ).model_dump()
        for r in rows
    ]
    return ApiResponse.ok(
        data=ThemeDetail(
            id=t.id,
            name=t.name,
            is_builtin=bool(t.is_builtin),
            keywords=t.keywords,
            stocks=stocks,
        ).model_dump()
    )


# ---------------------------------------------------------------------------
# LLM 配置
# ---------------------------------------------------------------------------
@router.get("/llm-config", response_model=ApiResponse)
def get_llm_config(db: Session = Depends(get_db)) -> ApiResponse:
    return ApiResponse.ok(data=_llm_status(db).model_dump())


@router.put("/llm-config", response_model=ApiResponse)
def update_llm_config(
    body: LlmConfigUpdate,
    test: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> ApiResponse:
    cfg = _get_llm_config(db)
    if body.api_base is not None:
        cfg.api_base = body.api_base.strip()
    if body.api_key is not None:
        cfg.api_key = body.api_key.strip()
    if body.model is not None:
        cfg.model = body.model.strip()

    configured = bool(cfg.api_base and cfg.api_key and cfg.model)
    if body.enabled is not None:
        # 双重大门：启用前校验三项齐全
        if body.enabled and not configured:
            return ApiResponse.error(message="启用前请填写 api_base / api_key / model 三项")
        cfg.enabled = bool(body.enabled)
    db.commit()

    status = _llm_status(db)
    extra: dict = {}
    if test:
        extra["test"] = test_llm_connection(db)
    return ApiResponse.ok(data={**status.model_dump(), **extra})


# ---------------------------------------------------------------------------
# 智能匹配 + 概念补全
# ---------------------------------------------------------------------------
@router.post("/smart-match", response_model=ApiResponse)
def smart_match_endpoint(
    body: SmartMatchRequest, db: Session = Depends(get_db)
) -> ApiResponse:
    try:
        stocks = smart_match(db, body.event_name, body.description)
    except LlmNotConfiguredError as e:
        return ApiResponse.error(message=str(e))
    except FetchError as e:
        return ApiResponse.error(message=str(e))
    data = [MatchedStock(**s).model_dump() for s in stocks]
    return ApiResponse.ok(data=data)


@router.get("/concept-stocks", response_model=ApiResponse)
def list_concept_stocks(
    concept: str = Query(..., min_length=1), db: Session = Depends(get_db)
) -> ApiResponse:
    try:
        stocks = fetch_concept_stocks_em(concept)
    except FetchError as e:
        return ApiResponse.error(message=str(e))
    data = [{"symbol": s.symbol, "name": s.name} for s in stocks]
    return ApiResponse.ok(data=data)


# ---------------------------------------------------------------------------
# 事件 CRUD
# ---------------------------------------------------------------------------
@router.post("", response_model=ApiResponse)
def create_event(body: EventCreate, db: Session = Depends(get_db)) -> ApiResponse:
    ev = Event(
        name=body.name.strip(),
        event_date=body.event_date,
        description=body.description,
        theme_id=body.theme_id,
    )
    db.add(ev)
    db.flush()  # 拿到 ev.id

    if body.stocks:
        for st in body.stocks:
            db.add(
                EventStock(
                    event_id=ev.id,
                    symbol=st.symbol.strip(),
                    chain_role=_norm_chain(st.chain_role),
                )
            )
    elif body.theme_id:
        # 从主题复制标的池（不污染模板）
        rows = (
            db.execute(select(ThemeStock).where(ThemeStock.theme_id == body.theme_id))
            .scalars()
            .all()
        )
        for r in rows:
            db.add(
                EventStock(
                    event_id=ev.id,
                    symbol=r.symbol,
                    chain_role=_norm_chain(r.chain_role),
                )
            )
    db.commit()
    db.refresh(ev)
    return ApiResponse.ok(data=_event_brief(db, ev).model_dump())


@router.get("/{event_id}", response_model=ApiResponse)
def get_event(event_id: int, db: Session = Depends(get_db)) -> ApiResponse:
    ev = db.get(Event, event_id)
    if ev is None:
        return ApiResponse.error(message="事件不存在")
    return ApiResponse.ok(data=_event_brief(db, ev).model_dump())


@router.put("/{event_id}/stocks", response_model=ApiResponse)
def update_event_stocks(
    event_id: int, body: EventStockUpdate, db: Session = Depends(get_db)
) -> ApiResponse:
    ev = db.get(Event, event_id)
    if ev is None:
        return ApiResponse.error(message="事件不存在")
    db.execute(EventStock.__table__.delete().where(EventStock.event_id == event_id))
    seen: set[str] = set()
    for st in body.stocks:
        sym = st.symbol.strip()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        db.add(
            EventStock(
                event_id=event_id,
                symbol=sym,
                chain_role=_norm_chain(st.chain_role),
            )
        )
    db.commit()
    db.refresh(ev)
    return ApiResponse.ok(data=_event_brief(db, ev).model_dump())


def _event_brief(db: Session, ev: Event) -> EventBrief:
    rows = (
        db.execute(select(EventStock).where(EventStock.event_id == ev.id))
        .scalars()
        .all()
    )
    stocks = [
        EventStockOut(symbol=r.symbol, name=_name_of(r.symbol), chain_role=r.chain_role)
        for r in rows
    ]
    return EventBrief(
        id=ev.id,
        name=ev.name,
        event_date=ev.event_date,
        description=ev.description,
        theme_id=ev.theme_id,
        stocks=stocks,
    )


# ---------------------------------------------------------------------------
# 三视图合并
# ---------------------------------------------------------------------------
@router.get("/{event_id}/impact", response_model=ApiResponse)
def get_impact(
    event_id: int,
    before: int = Query(default=20, ge=0, le=120),
    after: int = Query(default=20, ge=0, le=120),
    db: Session = Depends(get_db),
) -> ApiResponse:
    ev = db.get(Event, event_id)
    if ev is None:
        return ApiResponse.error(message="事件不存在")

    rows = (
        db.execute(select(EventStock).where(EventStock.event_id == ev.id))
        .scalars()
        .all()
    )
    if not rows:
        return ApiResponse.error(message="该事件尚未配置标的池")

    role_of: dict[str, str] = {r.symbol: r.chain_role for r in rows}
    symbols = [r.symbol for r in rows]
    ed = ev.event_date

    # 视图②：归一化收益曲线
    wr = event_impact.event_window_returns(db, symbols, ed, before, after)
    # 累计涨跌（排行榜）
    cum = event_impact.window_cumulative_change(db, symbols, ed, after)

    window_returns: dict[str, WindowReturnSeries] = {}
    for sym, series in wr.items():
        if not series:
            continue
        window_returns[sym] = WindowReturnSeries(
            dates=[d.isoformat() for d, _ in series],
            returns=[round(v, 4) for _, v in series],
        )

    # 基准（沪深300）
    bench_series_obj = event_impact.event_window_returns(
        db, [_BENCHMARK_SYMBOL], ed, before, after
    ).get(_BENCHMARK_SYMBOL, [])
    benchmark_series: WindowReturnSeries | None = None
    if bench_series_obj:
        benchmark_series = WindowReturnSeries(
            dates=[d.isoformat() for d, _ in bench_series_obj],
            returns=[round(v, 4) for _, v in bench_series_obj],
        )

    symbols_info = [
        SymbolInfo(symbol=sym, name=_name_of(sym), chain_role=role_of.get(sym, "midstream"))
        for sym in symbols
    ]

    ranking = sorted(
        (
            RankingItem(
                symbol=sym,
                name=_name_of(sym),
                change_pct=round(chg, 2),
                chain_role=role_of.get(sym, "midstream"),
            )
            for sym, chg in cum.items()
        ),
        key=lambda x: x.change_pct,
        reverse=True,
    )

    # 视图③：相关性矩阵（仅含有数据的标的，避免空行/空列噪声）
    corr_symbols = [s for s in symbols if s in window_returns]
    matrix = (
        event_impact.correlation_matrix(db, corr_symbols, ed, before, after)
        if len(corr_symbols) >= 2
        else [[1.0]] * 0  # 标的不足 → 空矩阵（前端按 corr_symbols 长度渲染）
    )
    if len(corr_symbols) < 2:
        matrix = []

    # 视图①：产业链分组
    groups = {"upstream": [], "midstream": [], "downstream": []}
    for sym in symbols:
        groups.setdefault(role_of.get(sym, "midstream"), []).append(sym)

    missing = [s for s in symbols if s not in window_returns]

    data = EventImpactData(
        event_id=ev.id,
        event_name=ev.name,
        event_date=ed,
        before=before,
        after=after,
        symbols_info=symbols_info,
        window_returns=window_returns,
        benchmark_symbol=_BENCHMARK_SYMBOL,
        benchmark_name=_BENCHMARK_NAME,
        benchmark_series=benchmark_series,
        ranking=ranking,
        correlation_symbols=corr_symbols,
        correlation_matrix=matrix,
        chain_groups=ChainGroups(**groups),
        missing=missing,
    )
    return ApiResponse.ok(data=data.model_dump(mode="json"))
