# 020 — 网格交易策略回测

## 目标

新增第五个策略回测页：**网格交易策略**。补齐策略武器库——MA120 吃趋势、回撤买入吃恐慌底，**网格吃震荡**。三者覆盖趋势/恐慌/震荡三种市场状态，形成完整组合。

**策略语义**：
- 用户设定**中枢价** + **网格间距 X%**（如每 3%）+ **每格资金 M**，系统自动生成上下网格线。
- 价格**跌破**某格基准线 → 买入一格（M 元）。
- 价格**涨破**某格基准线 → 卖出一格（当时买入的份额，锁定差价）。
- 循环套利，适合宽基/红利 ETF 的长期箱体震荡行情。

**核心创新（可视化驱动，契合项目风格）**：图表上直接**画出网格水平线**（ECharts markLine），每格标注价格与资金，已完成的格子变实色、未触发的虚色。一眼看清单子全貌与执行进度——这是网格策略最直观的呈现方式，远胜纯数字表格。

> **与现有策略的形态差异**：
> - 003 定投：按时间周期买入，不看价格。
> - 007 MA120：按均线信号波段买卖，吃趋势。
> - 015 回撤买入：价格跌到阈值累积买入，**单向只买**（除非 sell_mode 开启）。
> - **本策略**：价格穿越网格线**双向触发**，跌买涨卖，**吃震荡波动**。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（复用 `ensure_price_data`）
- [003 — 定投回测](./003-dca-compute-engine.md)（`annualized_return`/`xirr`/`max_drawdown` 公共函数）
- [007 — 红利 MA120 策略回测](./007-ma120-strategy-backtest.md)（**DB 持久化、task_id、图表范式、指标卡片的镜像模板**）

> 数据零新增：全部用 `raw_price_daily`。与 017/018 无依赖。

---

## Part A：后端

### 1. 计算引擎

新建 `backend/app/services/compute/grid.py`。

#### 1.1 网格生成

```python
def build_grid_levels(center_price: Decimal, step_pct: Decimal, n_above: int, n_below: int) -> list[Decimal]:
    """以 center 为中枢，按 step_pct 间距生成上下网格价。
    上方 n_above 格（center×(1+step), center×(1+2step), ...），下方 n_below 格对称。"""
```

- 网格线 = 中枢价 ± k×step（k=1..n）。
- 每格对应「一格资金 M」（买入金额）。

#### 1.2 交易逻辑（双向触发）

`GridParams`：

| 参数 | 说明 | 默认 |
|------|------|------|
| symbol | 标的 | 510300 |
| start_date / end_date | 区间 | 近 3 年 |
| center_price | 网格中枢价（元） | 区间起点收盘价 |
| step_pct | 网格间距 %（如 3） | 3 |
| amount_per_level | 每格资金 M（元） | 5000 |
| n_levels_above | 上方格数 | 5 |
| n_levels_below | 下方格数 | 5 |
| bound_mode | 突破网格上下沿处理：`hold`（持有等回归）/ `stop`（止损清仓）/ `reset`（重置中枢） | hold |

**触发规则**（逐日遍历收盘价）：
1. 维护 `last_level`（当前价格所在的网格区间索引）。
2. 当日价格从 `last_level` 跌穿到更低的格 → 对每跨过的一格**买入 M 元**（暴跌跨多格则多次买入）。
3. 当日价格从 `last_level` 突破到更高的格 → 对每跨过的一格**卖出一格持仓**（FIFO，卖出最早买入的份额，锁定差价）。
4. `bound_mode`：
   - `hold`：价格突破最高/最低格后不操作，等回归网格内再继续。
   - `stop`：突破下沿止损清仓（认亏）；突破上沿清仓（止盈）。
   - `reset`：突破后以新价格为中枢重置网格。

#### 1.3 逐日输出

每个交易日写：trade_date、signal（buy/sell/hold）、action_amount、holding_shares、cash_balance、cum_invested、cum_proceeds、market_value、pnl、return_rate、close、grid_index（当日所处网格区间索引）。

#### 1.4 task_id（镜像 007/019 范式）

```
grid_{symbol}_{start}_{end}_{center}_{step_pct}_{amount}_{n_above}_{n_below}_{bound_mode}_{source}
```

全参数确定性，非 akshare 源追加 `_{source}`。

### 2. 数据模型（镜像 MA120/drawboard）

#### 2.1 `calc_grid_backtest` 表（逐日）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| trade_date | DATE PK | |
| signal | VARCHAR(8) | buy/sell/hold |
| action_amount | DECIMAL(18,2) | |
| holding_shares | DECIMAL(20,8) | |
| cash_balance | DECIMAL(18,2) | 现金（cum_proceeds - cum_invested） |
| cum_invested | DECIMAL(18,2) | |
| cum_proceeds | DECIMAL(18,2) | 累计卖出回款 |
| market_value | DECIMAL(18,2) | holding×price + cum_proceeds |
| pnl | DECIMAL(18,2) | |
| return_rate | DECIMAL(12,4) | |
| close | DECIMAL(14,4) | |
| grid_index | INT | 当日所处网格区间索引（可负） |
| KEY idx_task (task_id) | | |

#### 2.2 `result_grid_summary` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| symbol | VARCHAR(32) | |
| center_price / step_pct / amount_per_level / n_above / n_below / bound_mode | | 参数 |
| start_date / end_date | DATE | |
| total_invested / final_value / total_pnl / total_return_rate / annualized_return / max_drawdown / buy_count / sell_count | | 与 007 同构 |
| grid_profit | DECIMAL(18,2) | **网格套利累计差价**（特色指标） |
| cycle_count | INT | 完成的买卖循环次数 |
| KEY idx_symbol (symbol) | | |

新建 `backend/app/models/grid.py`，注册 `models/__init__.py`。

### 3. SQL Migration

- `mysql/init/0X_grid.sql`：两张表 `CREATE TABLE IF NOT EXISTS`。
- `mysql/migrations/0XX_grid.sql`：已部署库用。
- 编号实施时按 `mysql/` 当前最大号 +1。

### 4. Schema（`schemas/grid.py`）

- `GridRequest`：上述 GridParams 全字段 + 校验（center_price>0、step_pct>0、amount>0、n_levels 1-20）
- `GridCreated`：task_id
- `GridChartData`：dates[]、close[]、market_value[]、total_cost[]、pnl[]、return_rate[]、signals[]、holding[]、buy_points[]、sell_points[]、**grid_levels[]（网格线价格数组，画 markLine 用）**、benchmark_returns[]、benchmark_name、symbol_name
- `GridSummaryData`：与 summary 表对应

> `grid_levels` 是本策略特色字段——前端据此画网格水平线。

### 5. API 路由（`api/grid.py`）

路由前缀 `/api/backtest/grid`（与 dca/ma120/drawboard 并列）：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/backtest/grid` | POST | 提交参数 → ensure_price_data → 计算 → 返回 task_id |
| `/api/backtest/grid/{task_id}/chart` | GET | 返回 GridChartData |
| `/api/backtest/grid/{task_id}/summary` | GET | 返回 GridSummaryData |

业务规则复用 007 范式：命中 `result_grid_summary` 直接返回；否则补数据 + 计算 + 写表。

### 6. 路由注册

`main.py`：`app.include_router(grid.router, prefix="/api/backtest", tags=["backtest"])`。

### 验收标准（后端）

- [ ] 网格生成正确（中枢对称、间距精确）
- [ ] 双向触发：跌穿买入、突破卖出，跨多格多次触发
- [ ] FIFO 卖出（卖出最早买入份额，锁定差价）
- [ ] bound_mode 三种各自正确
- [ ] grid_profit（套利差价）正确累计
- [ ] 两张表建成功 + task_id 幂等
- [ ] annualized/max_drawdown 正确
- [ ] 返回统一 ApiResponse，Swagger 可测

---

## Part B：前端（克隆 MA120 范式 + 网格 markLine）

### 1. 页面与表单（克隆 Ma120Backtest.vue）

新建 `frontend/src/views/GridBacktestView.vue`，表单结构对齐 MA120（`.form-card` + 两行 `.form-row` + 高级折叠）：

| 表单项 | 控件 | 默认 |
|--------|------|------|
| 标的代码 | 搜索输入（克隆 MA120 去抖+市场识别） | 510300 |
| 中枢价 | number | 区间首日收盘 |
| 网格间距 % | number | 3 |
| 每格资金 | number | 5000 |
| 上方格数 | number narrow | 5 |
| 下方格数 | number narrow | 5 |
| 突破处理 | select（hold/stop/reset） | hold |
| 起止日期 | date | 近 3 年 |
| 「开始回测」 | button.primary | |

### 2. 图表组件（`GridChart.vue`，克隆 Ma120Chart.vue + 网格线）

克隆 Ma120Chart 全套（生命周期/themeColors/三轴/堆叠柱/markPoint买卖点/tooltip formatter/legend/dataZoom），**新增网格 markLine**：

```ts
// 在收盘价 series 上加 markLine，画所有网格水平线
markLine: {
  symbol: 'none',
  silent: true,
  lineStyle: { type: 'dashed', width: 1, color: tc.axisLine },
  data: d.grid_levels.map(p => ({ yAxis: p, label: { formatter: p.toFixed(3), position: 'insideEndTop', fontSize: 10 } }))
}
```

- 网格线虚线、标注价格，与收盘价叠加。
- 买卖点 markPoint 落在收盘价线上（pin 红/蓝，同 MA120）。
- tooltip 克隆 MA120 风格，明细含：价格、当日网格区间、持仓、市值、盈亏、收益率、套利累计。

### 3. 指标卡片（克隆 MA120 cards）

| 卡片 | 字段 | 样式 |
|------|------|------|
| 累计投入 | total_invested | 默认 |
| 最终市值 | final_value | 默认 |
| 累计收益 | total_pnl | pnlColor |
| 累计收益率 | total_return_rate | pnlColor |
| 年化收益率 | annualized_return | pnlColor |
| 最大回撤 | max_drawdown | COLOR_DOWN |
| **网格套利** | grid_profit | pnlColor（**特色**） |
| 买卖次数 | 合并卡 buy_count/sell_count（克隆 MA120 `.trade-card`） | 红买蓝卖 |
| 完成循环 | cycle_count | 默认 |

### 4. 路由与导航

- `router/index.ts`：`{ path: '/grid', name: 'grid', component: GridBacktestView }`
- `App.vue` nav-links：`<RouterLink to="/grid">网格交易</RouterLink>`，排在「回撤看板」之后。

### 5. API 封装

`api/index.ts`：`createGrid`/`getGridChart`/`getGridSummary` + 类型 `GridParams`/`GridChartData`/`GridSummaryData`。

### 验收标准（前端）

- [ ] 导航「网格交易」入口
- [ ] 表单克隆 MA120 布局
- [ ] 图表显示**网格水平线**（markLine，虚线 + 价格标注）
- [ ] 买卖点 markPoint 红/蓝，与 MA120 一致
- [ ] tooltip/legend/三轴/堆叠柱与 MA120 一致
- [ ] 网格套利卡片正确
- [ ] 突破处理切换重算正确
- [ ] ?task= 预载可用（克隆 MA120 loadTask + parseGridTaskId）
- [ ] 明暗主题适配

---

## 数据复用与隔离

| 数据 | 来源 | 复用 |
|------|------|------|
| 行情 | raw_price_daily | ensure_price_data |
| 基准 | services/benchmark.py | 导入 |
| annualized/max_drawdown | compute/common.py | 公共函数 |
| DB/task_id/图表/卡片 | 007 MA120 | 整体克隆范式 |

> 低风险增量：计算逻辑（双向触发+FIFO）是新代码，其余全镜像 MA120。

---

## 开放问题

- [ ] **非对称网格**：上方间距大、下方间距小（适应慢涨急跌），一期对称。
- [ ] **动态中枢**：突破后自动重置中枢（bound_mode=reset 的细化）。
- [ ] **网格 + 趋势结合**：网格吃震荡、MA120 信号触发时暂停网格避趋势，组合策略。
- [ ] **多标的多网格**：一键跑多个 ETF 的网格对比（与 023 擂台联动）。
