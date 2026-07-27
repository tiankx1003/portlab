"""解析 ``docs/api-registry.yaml`` 契约表 → ToolSpec 列表。

契约表是「应该暴露什么」的单一事实源；tools/*.py 是「实际暴露什么」的实现。
启动时两者交叉校验：表里有但未注册 / 注册了但表里没有 → 告警（不阻断启动）。

不 import backend：``params_ref`` 仅作文档，入参 schema 在 tools/*.py 手写
（与 backend Pydantic 模型对齐，见各 tool 的函数签名 + docstring）。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ToolSpec:
    tool_name: str
    method: str
    path: str
    desc: str
    sample: str  # none / chart80 / event_impact
    group: str  # system / market / backtest / drawboard / event / arena


def load_registry(path: str | Path) -> list[ToolSpec]:
    """读 YAML，返回 expose=true 的 ToolSpec 列表。"""
    with open(path, encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    out: list[ToolSpec] = []
    for ep in doc.get("endpoints", []):
        mcp = ep.get("mcp") or {}
        if not mcp.get("expose"):
            continue
        out.append(
            ToolSpec(
                tool_name=mcp["tool_name"],
                method=ep["method"],
                path=ep["path"],
                desc=ep.get("desc", ""),
                sample=mcp.get("sample", "none"),
                group=mcp.get("group", "misc"),
            )
        )
    return out


def group_map(specs: list[ToolSpec]) -> dict[str, str]:
    """tool_name → group，供 /healthz 给已注册 tool 标分组。"""
    return {s.tool_name: s.group for s in specs}


def check_drift(specs: list[ToolSpec], registered_names: set[str]) -> list[str]:
    """返回漂移告警列表（表里有但没注册 / 注册了但表里没有）。空列表 = 无漂移。"""
    spec_names = {s.tool_name for s in specs}
    missing = sorted(spec_names - registered_names)
    extra = sorted(registered_names - spec_names)
    warns: list[str] = []
    if missing:
        warns.append(f"契约表声明暴露但未注册 tool：{missing}")
    if extra:
        warns.append(f"已注册但契约表未声明（将无法分组/可能漂移）：{extra}")
    return warns
