"""最近回测记录 schema（首页「最近回测记录」用）。"""

from pydantic import BaseModel


class RecentBacktestItem(BaseModel):
    task_id: str
    type: str  # 'dca' | 'ma120'
    symbol: str
    symbol_name: str
    return_rate: float
    period_text: str  # 起止日期区间
    created_text: str  # 记录时间近似值（取 end_date，两表无 created_at）
