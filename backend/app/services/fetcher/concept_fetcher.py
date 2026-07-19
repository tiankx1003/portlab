"""概念板块成分股拉取（事件冲击产业链看板 018，候选召回用）。

调东财概念板块接口（akshare ``stock_board_concept_*_em``）。注意：东财概念接口
**无腾讯回退**（akshare 未提供等价物），本机网络对东财接口阻断时本模块抛 ``FetchError``。
调用方（``services.matcher``）按 best-effort 处理 —— 召回失败不阻断 LLM 判定，
LLM 仍可凭自身知识给出候选标的。
"""

import os

os.environ.setdefault("TQDM_DISABLE", "1")  # 屏蔽 akshare 内部 tqdm

from dataclasses import dataclass

import akshare as ak

from .base import FetchError


@dataclass(frozen=True)
class ConceptStock:
    symbol: str
    name: str


def list_concept_names() -> list[str]:
    """东财全部概念板块名。失败抛 ``FetchError``。"""
    try:
        df = ak.stock_board_concept_name_em()
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"拉取概念板块列表失败: {e}") from e
    if df is None or df.empty:
        return []
    col = "板块名称" if "板块名称" in df.columns else df.columns[1]
    return [str(x).strip() for x in df[col].tolist() if str(x).strip()]


def fetch_concept_stocks_em(concept_name: str) -> list[ConceptStock]:
    """拉某概念板块成分股。失败抛 ``FetchError``。"""
    if not concept_name or not concept_name.strip():
        raise FetchError("概念名为空")
    try:
        df = ak.stock_board_concept_cons_em(symbol=concept_name.strip())
    except Exception as e:  # noqa: BLE001
        raise FetchError(f"拉取概念板块[{concept_name}]成分股失败: {e}") from e
    if df is None or df.empty:
        return []
    out: list[ConceptStock] = []
    for _, r in df.iterrows():
        code = str(r.get("代码", "")).strip()
        name = str(r.get("名称", "")).strip()
        if code:
            out.append(ConceptStock(symbol=code, name=name))
    return out
