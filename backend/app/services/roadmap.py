"""Roadmap 服务：解析 TASKS.md 中未实现任务（☐），与 docs/tasks 目录交叉校验。

TASKS.md 为真相源（状态 ☑/☐），目录扫描用于发现索引遗漏。进程内缓存避免每次请求读盘。
"""

import logging
import re
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CACHE_TTL = 300  # 5 分钟
_cache: dict = {"ts": 0.0, "data": None}

# 简单关键词归类（可选 category 字段）
_CATEGORY_KEYWORDS = [
    ("数据", ["数据源", "行情", "拉取", "tushare"]),
    ("策略", ["策略", "定投", "ma120", "回测"]),
    ("前端", ["首页", "导航", "前端", "页面", "ui"]),
    ("产品", ["反馈", "更新日志", "公告", "release"]),
]


def _find_repo_root() -> Path | None:
    """从本文件向上查找含 TASKS.md 的目录；再回退绝对路径候选（容器只读挂载 /repo）。"""
    here = Path(__file__).resolve()
    for parent in [here, *here.parents]:
        if (parent / "TASKS.md").exists():
            return parent
    for cand in (Path("/repo"),):
        if (cand / "TASKS.md").exists():
            return cand
    return None


def _categorize(title: str, summary: str) -> str:
    text = (title + " " + summary).lower()
    for cat, keywords in _CATEGORY_KEYWORDS:
        if any(kw in text for kw in keywords):
            return cat
    return "其他"


def _parse_tasks_md(text: str) -> list[dict]:
    """解析 TASKS.md 表格行（兼容 3 列与含「摘要」的 4 列）。"""
    items: list[dict] = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|") or "---" in s:
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) < 3:
            continue
        status = cells[-1]
        if status not in ("☑", "☐"):
            continue
        num = cells[0]
        if not re.fullmatch(r"\d{3}", num):
            continue
        m = re.match(r"\[(.+?)\]\((.+?)\)", cells[1])
        title = m.group(1) if m else cells[1]
        doc_url = m.group(2) if m else ""
        summary = cells[2] if len(cells) >= 4 else ""
        items.append(
            {"id": num, "title": title, "summary": summary, "doc_url": doc_url, "status": status}
        )
    return items


def _list_doc_ids(docs_dir: Path) -> set[str]:
    ids: set[str] = set()
    if not docs_dir.is_dir():
        return ids
    for p in docs_dir.iterdir():
        m = re.match(r"(\d{3})-", p.name)
        if m:
            ids.add(m.group(1))
    return ids


def get_roadmap() -> dict:
    """返回未实现任务（☐）列表，按编号升序。结果带 5 分钟进程缓存。"""
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < _CACHE_TTL:
        return _cache["data"]

    root = _find_repo_root()
    if root is None:
        logger.warning("roadmap: 未找到 TASKS.md（repo root 解析失败）")
        result = {"items": [], "total": 0}
        _cache.update(ts=now, data=result)
        return result

    all_items = _parse_tasks_md((root / "TASKS.md").read_text(encoding="utf-8"))
    doc_ids = _list_doc_ids(root / "docs" / "tasks")
    listed_ids = {it["id"] for it in all_items}

    # 交叉校验：文档存在但 TASKS.md 未登记 → 索引漏录告警
    for doc_id in doc_ids - listed_ids:
        logger.warning("roadmap: 文档 %s 存在但 TASKS.md 未登记（索引漏录）", doc_id)
    # TASKS.md 列出但文档不存在 → 死链告警
    for it in all_items:
        if it["doc_url"] and not (root / it["doc_url"]).exists():
            logger.warning("roadmap: TASKS.md 列出 %s 但文档不存在（死链）", it["id"])

    pending = sorted((it for it in all_items if it["status"] == "☐"), key=lambda x: x["id"])
    items = [
        {
            "id": it["id"],
            "title": it["title"],
            "summary": it["summary"],
            "doc_url": it["doc_url"],
            "category": _categorize(it["title"], it["summary"]),
        }
        for it in pending
    ]
    result = {"items": items, "total": len(items)}
    _cache.update(ts=now, data=result)
    return result
