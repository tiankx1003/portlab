"""MCP 状态接口 schema（026 Part C，供前端状态面板）。"""

from pydantic import BaseModel


class McpToolItem(BaseModel):
    name: str
    group: str
    desc: str


class McpStatusData(BaseModel):
    enabled: bool  # mcp 容器是否在线（/healthz 可达）
    mcp_url: str  # 宿主机访问地址（前端展示 + ZCode 配置复制）
    backend_reachable: bool  # mcp→backend 数据链路是否通
    tool_count: int
    tools: list[McpToolItem]
    last_check: str  # ISO 时间戳
