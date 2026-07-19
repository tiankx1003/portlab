# 015 — 基于最大回撤的买入策略看板（drawboard，拖拽驱动）

> **命名约定**：本功能实现时定名 **drawboard**（路由 `/api/drawboard`、文件 `drawboard.py`、视图 `DrawboardView.vue`）。本文档早期草稿曾用 `drawdown` 一词指代同一功能，2026-07 校正统一为 `drawboard`，与代码一致。下方涉及文件名/路径/路由处均用 `drawboard`。

## 目标

新增第四个图表页：**基于最大回撤的买入策略看板**。核心创新是**用图表拖拽交互定义买入策略**——拖动一条「回撤阈值线」即可实时调整买入条件，松手后重算买点与收益。

**默认标的**：`512890`（华泰柏瑞中证红利低波 ETF）。

**策略语义**：
- 价格从历史最高点**滚动回撤**达到阈值 T%（如 20%）→ 首次买入 A 元。
- 此后每再多跌 n% → 再加仓 m 元（金字塔分批，类 007 MA120 fixed 模式）。
- 拖动阈值线即调整 T，实时看到第一象限（价格区）的买点变化。

**图表四要素**：
- 横轴：日期。
- **左纵轴（单轴中间 0 线镜像）**：0 线之上画**收盘价**（正值），0 线之下画**滚动最大回撤%**（取负值，回撤越深线越靠下）。价格曲线与回撤曲线共用一条 0 基线，视觉镜像。
- **右纵轴**：市值（元）+ 收益率（%）。
- **基准**：沪深300（510300）收盘价叠加在左轴价格区对照（归一化或副轴）。

**核心交互**：一条可拖动的水平线位于左轴下半（回撤区），拖动时前端只移动线（不重算），**松手后**调后端按新阈值重算买点、市值、收益，结果回到第一象限显示。

> **与其他图表的形态差异**：
> - 003/007 是「参数表单 → 跑回测 → 看图」，参数在表单里填。
> - 本页是「**图表上直接拖拽 → 松手重算**」，参数（回撤阈值）通过交互可视化设定，表单只放资金参数（A/n/m）与区间。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)
- [003 — 定投回测：计算引擎、API 与前端](./003-dca-compute-engine.md)（复用 `ensure_price_data`、`benchmark` 计算）
- [007 — 红利 MA120 策略回测](./007-ma120-strategy-backtest.md)（fixed 资金模式范式、`Ma120Chart.vue` 图表范式）

> 与 012 无依赖：本页用 `raw_price_daily` 行情，不涉及资金流数据。

---

## Part A：后端

### 1. 计算引擎

新建 `app/services/drawboard.py`（实现时未放进 `compute/` 子目录，直接置于 `services/` 下）。

#### 1.1 滚动最大回撤（核心新计算）

现有 `compute/common.max_drawdown` 是「全序列单一值」，本任务需**逐日滚动回撤**：

```python
def rolling_drawdown(dates, closes) -> dict[date, Decimal]:
    """每个交易日 t 的回撤%：从区间起点到 t 的历史最高收盘价算起。
    返回 {date: drawdown_pct}，值恒 ≤ 0（取负，便于画在 0 线下方）。"""
    peak = closes[0]
    out = {}
    for d, c in zip(dates, closes):
        if c > peak:
            peak = c
        dd = (peak - c) / peak * 100 if peak > 0 else Decimal(0)
        out[d] = -dd  # 取负值
    return out
```

> 放入 `compute/common.py` 作为公共函数，供引擎与 API 共用。

#### 1.2 买入策略（fixed 金字塔分批，复用 007 范式）

`DrawboardParams`：

| 参数 | 说明 | 默认 |
|------|------|------|
| symbol | 标的 | 512890 |
| start_date / end_date | 区间 | 近 3 年 |
| threshold | 回撤买入阈值 T%（如 20） | 20 |
| principal | 首笔买入金额 A（元） | 10000 |
| step | 每再多跌 n% | 5 |
| add_amount | 每次加仓金额 m（元） | 5000 |
| sell_mode | 卖出方式：`none`（不卖）/ `new_high`（创新高清仓）/ `partial`（创新高卖一半） | none |

**买入规则**：
1. 当日滚动回撤绝对值 ≥ T → 首次买入 A。
2. 记录「上次买入时的回撤深度」`last_dd`，每较 `last_dd` 再深 `step`%（绝对值）→ 加仓 m。
3. 资金用尽不再买（若引入本金上限）。
4. **不止损**。

**卖出规则**（一期可选，默认 `none` 不卖）：
- `new_high`：当日收盘创新高（回撤回到 0）→ 清仓。
- `partial`：创新高卖出 50%。

#### 1.3 逐日计算输出

每个交易日写：trade_date、signal（buy/sell/hold）、action_amount、holding_shares、cash_balance、cum_invested、market_value、pnl、return_rate、drawdown（当日滚动回撤%，负值）、close、benchmark_close。

#### 1.4 task_id（幂等，复用 007 范式）

```
dd_{symbol}_{start}_{end}_{threshold}_{principal}_{step}_{add_amount}_{sell_mode}
```

全部参数确定性生成，相同参数重复执行幂等（先删后写）。

### 2. 数据模型

#### 2.1 `calc_drawboard_backtest` 表（逐日）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | 任务 ID |
| trade_date | DATE PK | 交易日 |
| signal | VARCHAR(8) | buy/sell/hold |
| action_amount | DECIMAL(18,2) | 当日操作金额 |
| holding_shares | DECIMAL(20,8) | 持仓份额 |
| cash_balance | DECIMAL(18,2) | 现金余额 |
| cum_invested | DECIMAL(18,2) | 累计投入 |
| market_value | DECIMAL(18,2) | 当日市值 |
| pnl | DECIMAL(18,2) | 盈亏 |
| return_rate | DECIMAL(12,4) | 收益率(%) |
| drawdown | DECIMAL(8,4) | 当日滚动回撤(%)，负值 |
| close | DECIMAL(14,4) | 当日收盘（冗余） |
| benchmark_close | DECIMAL(14,4) | 沪深300当日收盘（冗余） |

#### 2.2 `result_drawboard_summary` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| symbol | VARCHAR(32) | |
| threshold | DECIMAL(8,4) | 回撤阈值 |
| principal | DECIMAL(18,2) | 首笔金额 |
| step | DECIMAL(8,4) | 加仓步长 |
| add_amount | DECIMAL(18,2) | 加仓金额 |
| sell_mode | VARCHAR(8) | |
| start_date / end_date | DATE | |
| total_invested / final_value / total_pnl / total_return_rate / annualized_return / max_drawdown / buy_count / sell_count | | 与 007 summary 同构 |

新建 `backend/app/models/drawboard.py`，在 `models/__init__.py` 注册。

### 3. SQL Migration

- **`mysql/init/0X_drawboard.sql`**：两张表 `CREATE TABLE IF NOT EXISTS`。
- **`mysql/migrations/0XX_drawboard.sql`**：同样两张表，已部署库用。

### 4. Schema

新建 `backend/app/schemas/drawboard.py`：

- `DrawboardRequest`：symbol、start_date、end_date、threshold、principal、step、add_amount、sell_mode（校验：threshold>0、principal>0、step>0、add_amount>0）
- `DrawboardCreated`：task_id
- `DrawboardChartData`：dates[]、close[]、drawdown[]（负值）、market_value[]、return_rate[]、benchmark_close[]、signals[]、buy_points[]、sell_points[]
- `DrawboardSummaryData`：与 summary 表对应 + symbol_name

### 5. API 路由

新建 `backend/app/api/drawboard.py`，路由前缀 `/api/drawboard`（实现时未并入 `/api/backtest`，独立成 `/api/drawboard`）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/drawboard/backtest` | GET | 实时重算（实现时采用无状态 GET，非 POST） |
| `/api/drawboard/series` | GET | 行情 + 回撤序列（图表底图） |

**业务规则**（复用 007 范式）：
- **实现说明**：v1 交付时简化为**无状态 GET**（每次请求重算，不落库、无 task_id 幂等）。原设计的 POST 创建 + 命中缓存 + 写表模式**未实现**，见文末「实现偏离记录」与任务 019。
- `ensure_price_data` 补拉行情（含标的与沪深300基准）。
- 返回统一 `ApiResponse`。

### 6. 路由注册

`backend/app/main.py`：

```python
from .api import ..., drawboard, ...
app.include_router(drawboard.router, prefix="/api/drawboard", tags=["drawboard"])
```

### 验收标准（后端）

- [ ] 滚动回撤正确计算（峰值更新、回撤取负、与峰值重合日为 0；v1 内联于 `drawboard.py`，未抽到 `compute/common`）
- [ ] 金字塔分批买入逻辑正确：首次达阈值买入 A，每再深 step 加仓 m
- [ ] ~~卖出方式（none/new_high/partial）各自正确~~ → **v1 仅实现 new_high 硬编码，none/partial 未实现**（见偏离记录）
- [ ] ~~计算结果写入 `calc_drawboard_backtest` 与 `result_drawboard_summary`~~ → **v1 未建表、未持久化**
- [ ] ~~相同参数重复执行幂等~~ → **v1 无 task_id、每次重算**
- [ ] 行情与基准复用 `ensure_price_data`，缺失时补拉
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. API 封装

`frontend/src/api/index.ts` 新增：

- `getDrawdownSeries(symbol, start, end)` → GET `/api/drawboard/series`
- `runDrawdownBacktest(params)` → GET `/api/drawboard/backtest`（实时重算）
- 类型 `DrawdownSeries`、`DrawPoint`、`DrawSummary`、`DrawBacktestResult`

> v1 未实现 POST 创建 / `getDrawdownChart` / `getDrawdownSummary`（无 task_id 体系）。

### 2. 路由与导航

- `router/index.ts` 新增 `{ path: '/drawboard', name: 'drawboard', component: DrawboardView }`
- `App.vue` `nav-links` 新增 `<RouterLink to="/drawboard">回撤看板</RouterLink>`。

### 3. 页面（`frontend/src/views/DrawboardView.vue`）

**布局（控件栏精简 + 大图主体）：**

```
┌─────────────────────────────────────────────────────┐
│  回撤买入策略看板     [标的 512890] [区间] [A] [n] [m] [卖出] [运行]│
├─────────────────────────────────────────────────────┤
│  [累计投入] [当前市值] [累计收益] [收益率] [年化] [最大回撤] [买/卖次数]│
├─────────────────────────────────────────────────────┤
│         ┃ 收盘价 / 市值 / 收益率                     │
│   价格  ┃      ╱╲      ╱── 市值                     │
│   (左+) ┃   ╱╲╱  ╲   ╱     ●买点(markPoint)        │
│    ─────┼────────────── 0 基线 ─────────────────    │ ← 0 线
│   回撤  ┃   ╲╱╲    ╲╱╲  ── 收益率                   │
│   (左-) ┃      ╲╱╲╱                              │
│         ┃ ┄┄┄┄┄┄┄┄┄┄ <- 拖动此线设阈值 (可拖) ┄┄  │ ← 拖拽阈值线
│         ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                  日期 (dataZoom)         右轴: 市值/收益率 │
└─────────────────────────────────────────────────────┘
```

**控件栏**（精简，因核心参数靠拖拽）：
- 标的搜索（默认 512890）、起止日期。
- 资金参数：首笔金额 A、步长 n%、加仓金额 m。
- 卖出方式：单选 none/new_high/partial。
- 「运行」按钮：用当前表单参数 + **当前拖拽阈值**提交后端。

### 4. 图表组件

> v1 未拆分独立图表组件，回撤图直接内联于 `DrawboardView.vue`（用 echarts.init）。

**克隆 `Ma120Chart.vue` 范式**，关键差异：

#### 4.1 左轴：单轴中间 0 线镜像

- 单个 `yAxis`（左），价格画在正值（0 之上），回撤画在负值（drawdown 已取负）。
- `yAxis: { type:'value', scale:true }` 让 ECharts 自动跨正负区间，0 线自然居中。
- 0 基线加粗显示（`splitLine` 在 0 值处强调，或用 `markLine` 画一条 0 线）。

#### 4.2 拖拽阈值线（核心交互）

用 ECharts `graphic` 元素实现一条水平线，约束在 y<0 区域：

```ts
graphic: [{
  type: 'line',
  // 拖拽：onDrag 时只更新 y 位置（不重算），并显示当前阈值
  ondrag: (e) => { updateThresholdLine(e.offsetY) },
  draggable: true,
  // 限制只能纵向拖、且 y < 0
}]
```

- **拖动时**：前端仅移动线 + 实时显示「当前阈值：-T%」（tooltip 或角标）。
- **松手时**（`ondragend`）：触发查询——把新阈值 T（绝对值）连同表单资金参数调 `runDrawdownBacktest`，返回后刷新买点、市值、收益曲线。
  > v1 实现改用滑块控件（`<input type="range" min=3 max=50>`）+ watch 松手重算，未实现 graphic 拖拽线（见偏离记录）。
- 默认阈值 = 表单 threshold（初次进入或表单运行时设定）。

> 因「松手调后端」，拖拽不依赖前端计算引擎，复用 007 后端范式即可。

#### 4.3 四象限内容

- **第一象限（左轴上半，价格区）**：
  - 收盘价折线（主色）。
  - 沪深300 基准折线（虚线，归一化到同一起点便于对照，或副右轴）。
  - **买点 markPoint**（pin 标，COLOR_UP 红），买点坐标取自 `buy_points`（date + price）。
  - 卖点 markPoint（若有，COLOR_DOWN 绿）。
- **第四象限（左轴下半，回撤区）**：
  - 回撤曲线（取负值的 drawdown，单条折线，浅色）。
  - 拖拽阈值线（虚线，醒目色，带「阈值 -T%」标签）。
- **右轴**：市值折线 + 收益率折线（双右轴或共用，scale）。

#### 4.4 tooltip

`trigger:'axis'` + 自定义 formatter，按 dataIndex 显示：日期、收盘、当日回撤%、阈值、信号、持仓、市值、收益率、沪深300。

#### 4.5 其他

- `setOption(opt, true)` 全量替换、resize、dispose、watch(theme) 照搬。
- `themeColors()` 主题调色板照搬。
- A 股色 `COLOR_UP='#ee6666'` / `COLOR_DOWN='#3ba272'`。
- dataZoom inside + slider 照搬。
- `LegendHint` 提示「拖动下方阈值线调整买入条件」。

### 5. 指标卡片

用 `MetricCard.vue` 横排：累计投入、当前市值、累计收益（红绿）、收益率（红绿）、年化、最大回撤、买入次数、卖出次数。

### 验收标准（前端）

- [ ] 导航新增「回撤买入」入口
- [ ] 默认标的 512890，默认区间近 3 年
- [ ] 左轴单轴中间 0 线：上方价格、下方回撤（负值），0 线居中
- [ ] 拖拽阈值线可在回撤区（y<0）纵向拖动，拖动时实时显示当前阈值
- [ ] 松手后调后端重算，买点、市值、收益曲线刷新
- [ ] 第一象限显示买点 markPoint（红 pin），卖点（若有）
- [ ] 沪深300 基准叠加对照
- [ ] 右轴市值 + 收益率双曲线
- [ ] tooltip 显示当日完整明细
- [ ] 指标卡片数据正确
- [ ] 明暗主题切换后样式正确
- [ ] 复用 007 图表范式与 CSS 变量

---

## 数据复用与隔离策略

| 数据 | 来源 | 复用方式 |
|------|------|----------|
| 行情（512890 等） | `raw_price_daily` | `ensure_price_data` 补拉 |
| 基准（沪深300=510300） | `raw_price_daily` | 复用 `benchmark.py` 计算 |
| 滚动回撤计算 | 内联于 `drawboard.py`（v1 未抽公共函数） | `compute/common.rolling_drawdown` 待补（见 019） |
| 资金模式（fixed 金字塔） | 007 MA120 fixed 范式 | 逻辑同构，参数化复用 |
| task_id 幂等 | 007 范式 | **v1 未实现**，见 019 |

> **关键原则**：不新建行情表，全部从 `raw_price_daily` 读；计算结果**v1 未落库**，目标落 `calc_drawboard_backtest` + `result_drawboard_summary`（见 019）。

---

## 实现偏离记录（v1 交付物快照，2026-07 评审）

本节诚实记录 015 v1 实际交付与上方设计的差异，作为已交付版本的历史快照。**修正这些偏离是 [019 — drawboard v2](./019-drawboard-v2.md) 的任务范围，不在本任务内回改。**

| 维度 | 本文档设计 | v1 实际交付 | 影响 |
|------|-----------|-------------|------|
| **命名** | drawdown | **drawboard**（路由 `/api/drawboard`、文件 `drawboard.py`、视图 `DrawboardView.vue`） | 已于 2026-07 校正本文档术语对齐代码；代码命名保留 |
| **sell_mode** | none/new_high/partial 三模式，**默认 none** | **硬编码 new_high**，无开关、无参数 | 无法只买不卖（用户最初设想丢失）；见 019 |
| **DB 持久化** | `calc_drawboard_backtest` + `result_drawboard_summary` 两张表 | **未建表**，纯无状态每次重算 | 结果无法被首页「最近记录」引用 |
| **task_id 幂等** | `make_task_id` 命中缓存 | **无 task_id**，每次重算 | 重复参数无缓存收益 |
| **参数默认值** | threshold=20, step=5, add_amount=5000 | threshold=**10**, step=**2**, add_amount=**10000** | 偏离设计值 |
| **起始日期** | 近 3 年（动态） | 写死 `2022-01-01` | 不随时间滚动 |
| **annualized_return** | 复用 `common.annualized_return`/`xirr` | **未计算** | 缺年化指标 |
| **max_drawdown** | 复用 `common.max_drawdown` | **未计算**（虽算了滚动回撤序列，但未汇总） | 缺最大回撤汇总 |
| **拖拽交互** | ECharts `graphic` 可拖阈值线 | 改用滑块 `<input type=range>` + watch | 交互形态简化，未实现图形拖拽 |
| **图表组件** | 独立 `DrawdownChart.vue` | 内联于 `DrawboardView.vue` | 未拆分 |
| **benchmark** | 复用 `services/benchmark.py` | 本地重复定义 `BENCHMARK_SYMBOL="510300"` | 代码重复 |
| **rolling_drawdown** | 抽到 `compute/common.py` 公共函数 | 内联于 service | 未复用 |

> **结论**：v1 是可用的 MVP（拖滑块实时看回撤与买点），但 sell_mode 丢失、无持久化、参数偏离三项是与设计/用户初衷的主要差距，由 019 系统性补齐。

---

## 开放问题（后续迭代）

- [ ] **拖动实时预览**：一期松手调后端；后续可把价格序列传前端，拖动时实时本地预览买点（不调后端），松手才落库。
  > **更新（019）**：019 决定**放弃拖拽/滑块交互**，回撤阈值改为输入框 + 「开始回测」按钮显式触发，与 MA120 看板交互一致。本条「拖动实时预览」不再作为近期方向。
- [ ] **本金上限**：一期假设无限资金；后续加 `max_capital`，用尽停买。
- [ ] **回撤窗口限定**：一期从区间起点算滚动峰值；后续支持「近 N 日峰值」滚动窗口。
- [ ] **阈值预设快捷**：一键 -15% / -20% / -30% 常用阈值按钮。
- [ ] **多标的对比**：同阈值跑多个 ETF 横向比较。
- [ ] **回撤 vs MA120 组合**：回撤阈值 + MA 信号叠加策略。
