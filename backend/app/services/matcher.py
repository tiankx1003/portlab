"""智能匹配（事件 → 相关标的 + 产业链角色）。

核心能力（本看板卖点）：解决「朋友不知道有哪些相关股」的真问题。两步——

1. **概念板块召回**（best-effort 候选池）：用事件关键词扫东财全部概念板块名，召回相关概念
   及其成分股作为候选。本机对东财接口阻断时召回失败，**不阻断流程**（候选为空，LLM 仍可
   凭自身 A 股知识给出标的）。
2. **LLM 判定（必须）**：把事件描述 + 候选标的喂给 OpenAI 兼容协议的大模型，让它判定每只
   标的是否真相关、产业链角色、相关度权重，返回结构化 JSON。

**LLM 强依赖**：``enabled=0`` 或三项配置（api_base/api_key/model）不齐时，``smart_match``
抛 ``LlmNotConfiguredError``，由 API 层转 ``ApiResponse.error``，**不降级为概念板块伪结果**。

配置优先级：DB ``llm_config``（UI 主入口）> 环境变量 ``LLM_API_BASE/KEY/MODEL``（headless 兜底）。
启动时若 DB 行字段空而 env 有值，会自动 seed 进 DB（见 ``bootstrap_llm_config_from_env``）。
"""

import json
import logging
import re
from dataclasses import dataclass
from urllib import error as urlerror
from urllib import request as urlrequest

from sqlalchemy.orm import Session

from ..config import settings
from ..models.llm_config import LlmConfig
from .fetcher.base import FetchError

logger = logging.getLogger(__name__)

# LLM 调用参数
_LLM_TIMEOUT = 30
_LLM_MAX_TOKENS = 2000
_LLM_TEMPERATURE = 0.2
# 召回候选上限（控 prompt 体积 + 限频）
_MAX_RECALL_CONCEPTS = 6
_MAX_CANDIDATES = 80

_SYSTEM_PROMPT = (
    "你是 A 股产业链分析助手。根据给定事件，判断相关 A 股股票处在产业链哪个环节。\n"
    "产业链角色定义：\n"
    "- upstream：上游（原料种植 / 初级供给 / 资源端）\n"
    "- midstream：中游（加工 / 提取 / 制造 / 中间品）\n"
    "- downstream：下游（品牌 / 渠道 / 终端应用）\n"
    "relevance 取值：high(强相关) / medium(中等) / low(弱) / none(无关)。\n"
    "weight：0~1 的相关度权重（relevance 越高越大）。\n"
    "判断要点：紧扣事件本身的真实传导路径，剔除蹭概念的伪相关股；"
    "但绝大多数真实事件都至少波及 3~6 只相关标的，请尽力穷举（直接种植/加工/应用/替代品/受损/受益方）。\n"
    "若候选不足或候选均不相关、但你确知有真正相关的 A 股标的，可补充（须给出正确的 6 位代码与名称）。\n"
    "严格只输出 JSON，不要输出任何额外文字或 Markdown。schema：\n"
    '{"stocks":[{"symbol":"6位代码","name":"名称","chain_role":"upstream|midstream|downstream",'
    '"weight":0.0~1.0,"relevance":"high|medium|low|none"}]}\n'
    "只纳入 relevance != none 的标的；只有穷尽思考后确实找不出任何相关 A 股标的时，才返回 {\"stocks\":[]}。"
)

# 关键词停用词（召回时过滤无信息量 token）
_STOPWORDS = {
    "事件", "发生", "影响", "相关", "公司", "股票", "板块", "产业链",
    "什么", "哪些", "今天", "最近", "请问", "一下", "导致", "造成",
}


class LlmNotConfiguredError(Exception):
    """LLM 未配置或未启用，消息原样返回前端。"""


@dataclass
class LlmSettings:
    api_base: str
    api_key: str
    model: str
    enabled: bool

    @property
    def configured(self) -> bool:
        return bool(self.api_base and self.api_key and self.model)


# ---------------------------------------------------------------------------
# 配置解析
# ---------------------------------------------------------------------------
def resolve_llm_settings(db: Session) -> LlmSettings:
    """解析生效 LLM 配置：DB llm_config 优先，缺失字段回退环境变量。

    ``enabled``：DB 行存在时取 DB 开关；DB 行不存在（headless 全 env）时，
    三项 env 齐全视为启用，否则关闭。
    """
    cfg = None
    try:
        cfg = db.get(LlmConfig, 1)
    except Exception as e:  # noqa: BLE001 - 读取异常不阻断，回退 env
        logger.warning("读取 llm_config 失败，回退环境变量: %s", e)

    if cfg is not None:
        base = (cfg.api_base or "").strip() or settings.llm_api_base
        key = (cfg.api_key or "").strip() or settings.llm_api_key
        model = (cfg.model or "").strip() or settings.llm_model
        enabled = bool(cfg.enabled)
    else:
        base = settings.llm_api_base.strip()
        key = settings.llm_api_key.strip()
        model = settings.llm_model.strip()
        enabled = bool(base and key and model)  # headless：env 齐全即启用

    return LlmSettings(api_base=base, api_key=key, model=model, enabled=enabled)


def bootstrap_llm_config_from_env(db: Session) -> bool:
    """启动自愈：DB ``llm_config`` 行的 api_base 为空、而 env 三项齐全时，
    把 env 值 seed 进 DB 并置 enabled=1（让 ``.env`` 配置在 fresh 库上即时生效）。

    幂等：DB 任一字段已被 UI 写入（api_base 非空）则不覆盖。返回是否发生 seed。
    """
    env_base = settings.llm_api_base.strip()
    env_key = settings.llm_api_key.strip()
    env_model = settings.llm_model.strip()
    if not (env_base and env_key and env_model):
        return False
    cfg = db.get(LlmConfig, 1)
    if cfg is None:
        return False  # 行应由启动钩子保证存在
    if (cfg.api_base or "").strip():
        return False  # UI 已配置，不覆盖
    cfg.api_base = env_base
    cfg.api_key = env_key
    cfg.model = env_model
    cfg.enabled = True
    db.commit()
    logger.info("llm_config: 从环境变量 seed 连接配置并启用（model=%s）", env_model)
    return True


# ---------------------------------------------------------------------------
# 候选召回（best-effort）
# ---------------------------------------------------------------------------
def _cjk_ngrams(text: str, lo: int = 2, hi: int = 3) -> set[str]:
    """中文片段的 2~3 字 n-gram 集合（无分词器时的近似召回键）。

    例如「茉莉花产地受灾」→ {茉莉, 莉花, 花产, 产地, 地受, 受灾, 莉花产, 花产地, ...}。
    与概念板块名做 n-gram 交集命中即视为相关（需共享 ≥2 字连续子串，避免单字误匹配）。
    """
    grams: set[str] = set()
    for seg in re.findall(r"[一-龥]+", text or ""):
        for n in range(lo, hi + 1):
            for i in range(len(seg) - n + 1):
                g = seg[i : i + n]
                if g and g not in _STOPWORDS:
                    grams.add(g)
    return grams


def _recall_candidates(name: str, description: str | None) -> list[tuple[str, str]]:
    """概念板块召回候选 (symbol, name)。东财阻断或无命中时返回 []（best-effort）。"""
    from .fetcher.concept_fetcher import fetch_concept_stocks_em, list_concept_names

    event_grams = _cjk_ngrams(f"{name or ''} {description or ''}")
    if not event_grams:
        return []
    try:
        names = list_concept_names()
    except FetchError as e:
        logger.info("概念板块召回：拉取板块名失败（best-effort 跳过）: %s", e)
        return []

    hit: list[str] = []
    for cn in names:
        if event_grams & _cjk_ngrams(cn):
            hit.append(cn)
        if len(hit) >= _MAX_RECALL_CONCEPTS:
            break
    if not hit:
        return []

    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for cn in hit:
        try:
            stocks = fetch_concept_stocks_em(cn)
        except FetchError as e:
            logger.info("概念板块召回：[%s] 成分股拉取失败（跳过）: %s", cn, e)
            continue
        for st in stocks:
            if st.symbol in seen:
                continue
            seen.add(st.symbol)
            out.append((st.symbol, st.name))
            if len(out) >= _MAX_CANDIDATES:
                return out
    return out


# ---------------------------------------------------------------------------
# LLM 调用
# ---------------------------------------------------------------------------
def _resolve_endpoint(api_base: str) -> str:
    """OpenAI 兼容 endpoint：base 不以 /chat/completions 结尾则补上。"""
    b = api_base.strip().rstrip("/")
    if not b:
        raise FetchError("LLM api_base 为空")
    if b.endswith("/chat/completions"):
        return b
    return b + "/chat/completions"


def _call_llm(
    s: LlmSettings, system_prompt: str, user_content: str, *, json_mode: bool = True
) -> str:
    """OpenAI 兼容协议 POST /chat/completions，返回 assistant content。失败重试 1 次。

    用标准库 ``urllib`` 实现 —— 避免引入 httpx 依赖（部分部署环境 pypi 不可达）。
    """
    url = _resolve_endpoint(s.api_base)
    payload: dict = {
        "model": s.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": _LLM_MAX_TOKENS,
        "temperature": _LLM_TEMPERATURE,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {s.api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    last_err: FetchError | None = None
    for _ in range(2):  # 失败重试 1 次 → 共 2 次尝试
        req = urlrequest.Request(url, data=body, headers=headers, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=_LLM_TIMEOUT) as resp:  # noqa: S310
                raw = resp.read().decode("utf-8", errors="replace")
                status = resp.status
        except urlerror.HTTPError as e:
            txt = ""
            try:
                txt = e.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                pass
            last_err = FetchError(f"LLM 返回 HTTP {e.code}: {txt[:200]}")
            continue
        except Exception as e:  # noqa: BLE001
            last_err = FetchError(f"LLM 调用网络异常: {type(e).__name__}: {e}")
            continue
        if status != 200:
            last_err = FetchError(f"LLM 返回 HTTP {status}: {raw[:200]}")
            continue
        try:
            data = json.loads(raw)
            content = data["choices"][0]["message"].get("content") or ""
            return content
        except Exception as e:  # noqa: BLE001
            last_err = FetchError(f"LLM 返回结构异常: {e}；原始: {raw[:200]}")
            continue
    raise last_err or FetchError("LLM 调用失败")


def _build_user_prompt(
    name: str, description: str | None, candidates: list[tuple[str, str]]
) -> str:
    lines = [f"事件名称：{name}"]
    if description and description.strip():
        lines.append(f"事件描述：{description.strip()}")
    if candidates:
        lines.append("候选标的（代码 名称，来自相关概念板块召回）：")
        for sym, nm in candidates:
            lines.append(f"- {sym} {nm}")
        lines.append("请在上述候选基础上判定；若候选不足可补充你认为真正相关的 A 股标的。")
    else:
        lines.append("（候选召回为空）请直接根据你的 A 股知识，给出与该事件真正相关的标的。")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 解析
# ---------------------------------------------------------------------------
def _norm_role(v) -> str:
    r = str(v or "").strip().lower()
    return r if r in ("upstream", "midstream", "downstream") else "midstream"


def _norm_weight(v) -> float:
    try:
        w = float(v)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, w))


def _norm_relevance(v) -> str:
    r = str(v or "").strip().lower()
    return r if r in ("high", "medium", "low", "none") else "medium"


def _parse_llm_stocks(raw: str) -> list[dict]:
    """解析 LLM 返回 JSON → MatchedStock dict 列表。失败抛 FetchError。"""
    if not raw or not raw.strip():
        raise FetchError("LLM 返回空内容")
    try:
        obj = json.loads(raw)
    except Exception as e:
        raise FetchError(f"LLM 返回非 JSON，无法解析: {e}；原始返回: {raw[:300]}") from e
    stocks = obj.get("stocks") if isinstance(obj, dict) else None
    if not isinstance(stocks, list):
        raise FetchError(f"LLM 返回 JSON 缺少 stocks 字段；原始返回: {raw[:300]}")
    out: list[dict] = []
    for st in stocks:
        if not isinstance(st, dict):
            continue
        sym = str(st.get("symbol", "")).strip()
        if not sym:
            continue
        rel = _norm_relevance(st.get("relevance"))
        if rel == "none":
            continue  # 剔除无关
        out.append(
            {
                "symbol": sym,
                "name": str(st.get("name", "")).strip(),
                "chain_role": _norm_role(st.get("chain_role")),
                "weight": round(_norm_weight(st.get("weight")), 2),
                "relevance": rel,
            }
        )
    return out


# ---------------------------------------------------------------------------
# 对外入口
# ---------------------------------------------------------------------------
def smart_match(db: Session, event_name: str, description: str | None) -> list[dict]:
    """智能匹配：返回 MatchedStock dict 列表。

    - LLM 未启用 / 未配置 / 三项不齐 → 抛 ``LlmNotConfiguredError``（API 层转 error，不降级）。
    - LLM 返回非 JSON / 解析失败 → 抛 ``FetchError``。
    """
    s = resolve_llm_settings(db)
    if not s.enabled or not s.configured:
        raise LlmNotConfiguredError("未配置 LLM，请在「LLM 设置」中填写连接信息并开启")

    name = (event_name or "").strip()
    if not name:
        raise FetchError("事件名为空")

    candidates = _recall_candidates(name, description)
    if candidates:
        logger.info("智能匹配：召回候选 %d 只", len(candidates))
    user_prompt = _build_user_prompt(name, description, candidates)
    stocks: list[dict] = []
    # 推理模型偶发返回空结果（非确定性），空时再试一次（共 2 次）
    for attempt in range(2):
        raw = _call_llm(s, _SYSTEM_PROMPT, user_prompt, json_mode=True)
        stocks = _parse_llm_stocks(raw)
        if stocks:
            break
        if attempt == 0:
            logger.info("智能匹配：LLM 返回空，重试一次（attempt 2/2）")
    # 名称兜底：LLM 漏名称的用标的目录补
    if stocks:
        from . import symbol_catalog

        for st in stocks:
            if not st["name"]:
                nm = symbol_catalog.lookup_name(st["symbol"])
                if nm:
                    st["name"] = nm
    return stocks


def test_llm_connection(db: Session) -> str | None:
    """发极简 prompt 验证配置有效。返回错误信息或 None（None=成功）。

    用于 ``PUT /llm-config?test=true`` 连通性测试。
    """
    s = resolve_llm_settings(db)
    if not s.configured:
        return "配置不完整（api_base / api_key / model 三项必填）"
    try:
        _call_llm(s, "你是连通性测试助手。", "请回复 ok。", json_mode=False)
        return None
    except FetchError as e:
        return str(e)
