# 021 — 股息率 / DCF 估值回测

## 目标

新增第六个策略回测页：**股息率 / DCF 估值回测**。把 [016 估值温度计](./016-valuation-thermometer.md)（被动展示「贵不贵」）升级为**可回测的策略**——回答红利投资者最关心的：「**按当前这个估值买入，未来 N 年预期能赚多少、历史上这么买胜率多少**」。

**两种估值锚**（决定回测的「相同估值水平」如何定义）：

| 锚 | 数据来源 | 状态 | 说明 |
|----|----------|------|------|
| **股息率锚**（主） | 016 的股息率历史序列 | **⚠️ 依赖未就绪**（见下） | 红利策略最贴切的锚 |
| **PE 分位锚**（降级） | 016 的 PE 历史（lg/csindex 已有） | ✅ 可用 | 数据缺位时的 fallback |

> **⚠️ 前置依赖警告（决定性）**：
> 本任务的「股息率锚」模式**强依赖 016 提供股息率的完整历史日序列**。但 016 实测发现：akshare 1.18.64 的 csindex 接口仅返回**当日快照（~20天）**，**无历史序列**——这是 akshare 的数据限制，非代码问题。
> 因此本任务**一期先落地「PE 分位锚」模式**（016 的 PE 历史已可用），「股息率锚」作为**条件性功能**——待 016 通过「每日累积快照拼出股息率历史」（见 016 开放问题）就绪后启用。文档对两种模式都做完整设计，实施时按数据就绪情况切换。

**策略语义**：
- 用户选标的 + 选估值锚（股息率/PE 分位）+ 输入当前估值水平（或自动取最新）+ 持有年限 N + DCF 假设（股息增速 g / 要求回报率 r）。
- 系统**在历史上所有「相同估值水平」的日子**模拟买入，持有 N 年，统计实际收益分布。
- 输出：**预期年化 + 历史胜率 + 收益分布区间（25%/50%/75% 分位）**。

> **与 016 的关系**：016 是「看板」（当前估值多贵），本任务是「策略」（这个估值买入预期如何）。两者形成估值决策闭环。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（复用 `ensure_price_data`）
- [003 — 定投回测](./003-dca-compute-engine.md)（`annualized_return`/`xirr`/`max_drawdown`）
- [016 — 估值温度计](./016-valuation-thermometer.md)（**估值数据来源，强依赖**）
- [007 — MA120](./007-ma120-strategy-backtest.md)（DB/task_id/图表/卡片范式）

> **关键依赖**：016 的估值表 `raw_index_valuation_daily`（PE/PB/股息率）。PE 历史已就绪；股息率历史待 016 演进。

---

## Part A：后端

### 1. 计算引擎

新建 `backend/app/services/compute/valuation_backtest.py`。

#### 1.1 估值锚匹配（核心）

```python
def find_similar_valuation_dates(
    db, index_code: str, target_metric: str, target_value: Decimal,
    lookback_start: date, lookback_end: date, tolerance_pct: Decimal = Decimal(5)
) -> list[date]:
    """在历史中找出所有「估值与目标值相近」的日期。
    target_metric: 'dividend_yield' / 'pe_percentile' / 'pe_ttm'
    tolerance_pct: 容差%，如 5 表示目标值 ±5% 范围内都算「相似」。
    """
```

- 对每个候选买入日，从 `raw_index_valuation_daily` 读该日的 metric 值，判断是否落在 `[target×(1-tol), target×(1+tol)]`。
- `pe_percentile` 模式：先算目标 PE 在历史的分位，再找所有「分位相近」的日期。

#### 1.2 DCF / 戈登模型（预期收益推算）

```python
def expected_return(dividend_yield: Decimal, growth_rate: Decimal) -> Decimal:
    """戈登增长模型：预期收益 = 股息率 + 股息增速 g。
    完整 DCF 可选：对现金流逐期贴现求内在价值，再与当前价比较。"""
    return dividend_yield + growth_rate
```

- 用户输入 `g`（股息年增速，如 3%）、`r`（要求回报率，如 8%）。
- 输出「按当前估值买入的理论预期年化」。

#### 1.3 历史回测（持有 N 年的实际收益分布）

```python
def backtest_holding_returns(
    db, symbol: str, buy_dates: list[date], hold_years: int
) -> list[HoldingResult]:
    """对每个 buy_date，模拟买入并持有 hold_years 年，
    计算实际年化收益。返回所有样本的收益列表，供分布统计。"""
```

- 每个 buy_date 的收益 = `(close[buy_date + N年] / close[buy_date]) ^ (1/N) - 1`。
- 缺末日行情的样本跳过（或用最近可用日）。
- 统计：均值、中位数、25/75 分位、胜率（收益>0 占比）。

#### 1.4 task_id

```
valbt_{symbol}_{metric}_{target_value}_{hold_years}_{tolerance}_{source}
```

全参数确定性。

### 2. 数据模型

#### 2.1 `result_valuation_bt_summary` 表（汇总，无逐日表——本策略是分布统计非时序）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| symbol | VARCHAR(32) | |
| index_code | VARCHAR(16) | 跟踪指数 |
| metric | VARCHAR(16) | dividend_yield / pe_percentile / pe_ttm |
| target_value | DECIMAL(12,4) | 目标估值 |
| tolerance_pct | DECIMAL(8,4) | 容差 |
| hold_years | INT | 持有年限 |
| growth_rate | DECIMAL(8,4) | DCF 假设 g |
| sample_count | INT | 匹配到的历史样本数 |
| win_rate | DECIMAL(8,4) | 胜率(%) |
| mean_return / median_return / p25_return / p75_return | DECIMAL(12,4) | 收益分布(年化%) |
| expected_return | DECIMAL(12,4) | DCF 理论预期年化(%) |
| start_date / end_date | DATE | 回看区间 |
| KEY idx_symbol (symbol) | | |

> 无 calc 逐日表——本策略输出是「分布统计」+「各样本买入点」，不是连续时序。

#### 2.2 `calc_valuation_bt_samples` 表（各历史样本明细，供散点图）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| buy_date | DATE PK | 历史买入日 |
| metric_value | DECIMAL(12,4) | 该日估值 |
| end_date | DATE | 持有结束日 |
| annualized_return | DECIMAL(12,4) | 实际年化(%) |
| total_return | DECIMAL(12,4) | 总收益(%) |

新建 `backend/app/models/valuation_bt.py`，注册 `models/__init__.py`。

### 3. SQL Migration

- `mysql/init/0X_valuation_bt.sql`：两张表。
- `mysql/migrations/0XX_valuation_bt.sql`：已部署库用。

### 4. Schema（`schemas/valuation_bt.py`）

- `ValuationBtRequest`：symbol、metric（dividend_yield/pe_percentile/pe_ttm）、target_value（可选，缺省取最新）、tolerance_pct、hold_years、growth_rate、lookback（5y/10y/since_inception）
- `ValuationBtResult`：summary 全字段 + `samples[]`（各历史样本）+ `distribution`（收益直方图分桶）+ `expected_return`

### 5. API 路由（`api/valuation_bt.py`）

路由前缀 `/api/backtest/valuation`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/backtest/valuation` | POST | 提交参数 → ensure 估值+行情 → 匹配+回测 → 落库 → 返回 task_id |
| `/api/backtest/valuation/{task_id}` | GET | 返回 ValuationBtResult（summary + samples + distribution） |

业务规则：
- **metric=dividend_yield 时**：检查 `raw_index_valuation_daily` 是否有该指数的股息率历史（非全 NULL）；**若无可得数据，返回 `ApiResponse.error("股息率历史数据未就绪，请改用 PE 分位模式或等待 016 数据补充")`**。
- metric=pe_percentile/pe_ttm 时正常。
- 命中缓存直接返回。

### 6. 路由注册

`main.py`：`app.include_router(valuation_bt.router, prefix="/api/backtest", tags=["backtest"])`。

### 验收标准（后端）

- [ ] PE 分位锚模式完整可用（一期主路径）
- [ ] 股息率锚模式：数据就绪时可用，未就绪时返回明确错误（不崩）
- [ ] 戈登模型 expected_return 正确
- [ ] 历史样本匹配 + 持有 N 年收益计算正确
- [ ] 胜率、分布分位正确
- [ ] 两张表建成功 + task_id 幂等
- [ ] 返回统一 ApiResponse，Swagger 可测

---

## Part B：前端（克隆 MA120 表单/卡片 + 散点分布图）

### 1. 页面与表单（克隆 Ma120Backtest.vue）

新建 `frontend/src/views/ValuationBtView.vue`：

| 表单项 | 控件 | 默认 |
|--------|------|------|
| 标的代码 | 搜索输入（克隆 MA120） | 512890 |
| 估值锚 | select（pe_percentile/pe_ttm/dividend_yield） | pe_percentile |
| 目标估值 | number（可选，缺省取最新） | 自动 |
| 容差 % | number | 5 |
| 持有年限 | number | 3 |
| 股息增速 g % | number（DCF 假设） | 3 |
| 回看窗口 | select（5y/10y/since_inception） | 10y |
| 「开始回测」 | button.primary | |

- 选 dividend_yield 时，若后端报「数据未就绪」，前端醒目提示并建议切 PE 分位。

### 2. 图表（两种，都克隆 MA120 主题/配色）

#### 2.1 收益分布图（`ValuationBtDistChart.vue`）

- **直方图**（ECharts bar）：横轴年化收益分桶，纵轴样本数。标出当前 DCF 预期收益位置（markLine）。
- **散点图**（ECharts scatter，可选叠加）：横轴买入日期、纵轴实际年化，每个历史样本一点，颜色按盈亏（红赚绿亏）。

#### 2.2 累积净值参考线（可选）

- 画「所有样本买入日起的净值中位数曲线」+ 25/75 分位带，展示典型持有路径。

### 3. 指标卡片（克隆 MA120 cards）

| 卡片 | 字段 | 样式 |
|------|------|------|
| 样本数 | sample_count | 默认 |
| 历史胜率 | win_rate | pnlColor |
| 平均年化 | mean_return | pnlColor |
| 中位年化 | median_return | pnlColor |
| 25 分位 | p25_return | COLOR_DOWN |
| 75 分位 | p75_return | COLOR_UP |
| DCF 预期 | expected_return | 主色 |

### 4. 路由与导航

- `router/index.ts`：`{ path: '/valuation-bt', name: 'valuation-bt', component: ValuationBtView }`
- `App.vue` nav-links：`<RouterLink to="/valuation-bt">估值回测</RouterLink>`，排在「网格交易」之后。

### 5. API 封装

`api/index.ts`：`createValuationBt`/`getValuationBtResult` + 类型。

### 验收标准（前端）

- [ ] 导航「估值回测」入口
- [ ] 表单克隆 MA120 布局
- [ ] PE 分位模式完整可用
- [ ] 股息率模式未就绪时友好提示 + 建议切换
- [ ] 收益分布直方图正确（标 DCF 预期位置）
- [ ] 散点图按盈亏分色
- [ ] 指标卡片正确
- [ ] ?task= 预载可用
- [ ] 明暗主题适配

---

## 数据复用与隔离

| 数据 | 来源 | 复用 |
|------|------|------|
| PE/PB/股息率 | 016 `raw_index_valuation_daily` | **强依赖** |
| 行情 | raw_price_daily | ensure_price_data |
| annualized/max_drawdown | compute/common.py | 公共函数 |
| DB/task_id/图表/卡片 | 007 MA120 | 克隆范式 |

> 本任务几乎不新建数据——核心是「消费 016 的估值数据 + 套用回测统计」。风险点全在 016 的股息率历史可得性。

---

## 开放问题

- [ ] **股息率历史就绪**：依赖 016 通过每日累积 csindex 快照拼出股息率序列（016 开放问题）。就绪前本任务仅支持 PE 锚。
- [ ] **完整 DCF**：一期用戈登简化模型；后续支持逐期现金流贴现（需预测股息路径）。
- [ ] **多估值锚组合**：同时满足「股息率高于 X 且 PE 分位低于 Y」的买入条件。
- [ ] **动态持有期**：一期固定 N 年；后续支持「持有至估值回归某水平即卖出」。
- [ ] **与 015 回撤买入结合**：估值低 + 回撤深的「双低」买入条件。
