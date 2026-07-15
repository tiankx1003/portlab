# 007 — 红利 MA120 策略回测

## 目标

在现有定投回测工具旁新增一个并列的独立回测工具——「红利 MA120 策略回测」。
基于「红利 ETF + MA120 均线」波段策略，在 MA120 下方金字塔分批买入、MA120 上方分批/全部卖出，
支持固定本金、持续投入、混合三种资金模式。

行情数据**复用 `raw_price_daily` 已有数据**，通过统一的 `_ensure_data` 补拉缺失区间，避免重复请求。

> 策略参考：`docs/refer/收割机修订版_红利ETF_MA120策略.md`

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)
- [003 — 定投回测：计算引擎、API 与前端](./003-dca-compute-engine.md)

> 与 006（智能定投）无依赖关系，两者并列同级。

## Part A：MA120 策略计算引擎

### 新增文件

- `app/services/compute/ma120.py` — MA120 策略回测计算引擎

### 设计要点

#### 数据复用

- 从 `raw_price_daily` 读取行情（与 DCA 引擎共用同一张表、同一数据源）
- 调用现有 `_ensure_data()` 逻辑（从 `api/backtest.py` 中提取为公共函数或直接 import）确保数据完整
- MA 计算需回溯额外 `ma_period * 2` 天的日历日（与 DCA 智能定投 `lookback_days` 一致）

#### 资金模式

| 模式 | 说明 | 参数 |
|------|------|------|
| `fixed` | 初始本金一笔到位，分成 N 份，按策略逐份使用 | `principal`（初始本金）, `splits`（份数，默认 10） |
| `recurring` | 无初始本金，每月新增资金累积入资金池，按策略从池中取用 | `monthly_amount`（每月投入） |
| `hybrid` | 初始本金 + 每月追加，资金池 = 剩余本金 + 月度新增 | `principal` + `monthly_amount` |

#### 买入规则

1. **触发条件**：当日收盘价 < MA(ma_period) × `buy_threshold`（默认 0.985）
2. **首次买入**：触发时使用 1 份资金买入
3. **加仓规则**：每较上次买入价再跌 `step`（默认 0.01）加仓 1 份
4. **暴跌加倍**：单日跌幅 ≥ `crash_threshold`（默认 5%）时，加仓份数 × `crash_multiplier`（默认 2）
5. **资金用尽**：资金池为 0 时不再买入
6. **不止损**

#### 卖出规则

| 卖出方式 | 说明 |
|----------|------|
| `batch` | 站回 MA 上方后，每涨一定幅度卖出一批（默认每涨 2% 卖 1/splits 仓位） |
| `all` | 站回 MA 上方当日全部清仓 |
| `half` | 站回 MA 上方卖出 50% 仓位，留底仓等下次跌破再买 |

#### 分红处理

- `cash`：分红金额记入 `cash_balance`，不增加份额
- `reinvest`：按除息日收盘价将分红折算为份额（需要分红数据，一期可先支持 `cash`，`reinvest` 标为 TODO）

#### 逐日计算

每个交易日计算并写入：

| 指标 | 说明 |
|------|------|
| trade_date | 交易日 |
| signal | `buy` / `sell` / `hold` |
| action_shares | 当日买入（+）或卖出（-）份额 |
| action_amount | 当日买入/卖出金额 |
| holding_shares | 持仓份额 |
| cash_balance | 现金余额（分红现金 + 卖出回款 - 买入支出） |
| cum_invested | 累计投入本金 |
| market_value | 当日市值（持仓份额 × 收盘价 + 现金） |
| pnl | 盈亏 = 市值 - 累计投入 |
| return_rate | 收益率 = 盈亏 / 累计投入 × 100% |
| ma_value | 当日 MA120 值 |
| price_vs_ma | 价格相对 MA 的偏离度（%） |

### 数据模型

#### `calc_ma120_backtest` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | 任务 ID |
| trade_date | DATE PK | 交易日 |
| signal | VARCHAR(8) | buy/sell/hold |
| action_shares | DECIMAL(20,8) | 当日操作份额（买入为正，卖出为负，无操作为 0） |
| action_amount | DECIMAL(18,2) | 当日操作金额 |
| holding_shares | DECIMAL(20,8) | 持仓份额 |
| cash_balance | DECIMAL(18,2) | 现金余额 |
| cum_invested | DECIMAL(18,2) | 累计投入本金 |
| market_value | DECIMAL(18,2) | 当日总市值（持仓 + 现金） |
| pnl | DECIMAL(18,2) | 盈亏 |
| return_rate | DECIMAL(12,4) | 收益率(%) |
| ma_value | DECIMAL(14,4) | 当日均线值 |
| price_vs_ma | DECIMAL(8,4) | 价格相对 MA 偏离度(%) |

#### `result_ma120_summary` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | 任务 ID |
| symbol | VARCHAR(32) | 标的代码 |
| capital_mode | VARCHAR(16) | fixed/recurring/hybrid |
| principal | DECIMAL(18,2) | 初始本金（fixed/hybrid） |
| monthly_amount | DECIMAL(18,2) | 月度投入（recurring/hybrid） |
| splits | INT | 份数 |
| ma_period | INT | 均线周期 |
| buy_threshold | DECIMAL(8,4) | 起始买入阈值 |
| step | DECIMAL(8,4) | 加仓步长 |
| sell_mode | VARCHAR(8) | batch/all/half |
| start_date | DATE | 回测开始日期 |
| end_date | DATE | 回测结束日期 |
| total_invested | DECIMAL(18,2) | 累计投入 |
| final_value | DECIMAL(18,2) | 最终市值 |
| total_pnl | DECIMAL(18,2) | 累计盈亏 |
| total_return_rate | DECIMAL(12,4) | 累计收益率(%) |
| annualized_return | DECIMAL(12,4) | 年化收益率(%)（XIRR） |
| max_drawdown | DECIMAL(12,4) | 最大回撤(%) |
| buy_count | INT | 买入次数 |
| sell_count | INT | 卖出次数 |
| dividend_total | DECIMAL(18,2) | 累计分红 |
| win_rate | DECIMAL(8,4) | 胜率(%) |

### task_id 规则

```
ma120_{symbol}_{start}_{end}_{mode}_{principal}_{monthly}_{splits}_{ma_period}_{buy_threshold}_{step}_{sell_mode}
```

全部参数确定性生成，保证幂等。

### 验收标准（计算引擎）

- [ ] fixed 模式：本金按份数分配，买入/卖出信号正确触发
- [ ] recurring 模式：每月月初资金到账，资金池正确扣减
- [ ] hybrid 模式：初始本金 + 月度追加正确组合
- [ ] 暴跌加倍逻辑正确触发
- [ ] 三种卖出方式各自正确执行
- [ ] MA120 计算正确（与 DCA 智能定投 `_compute_ma` 逻辑一致，可复用）
- [ ] 计算结果写入 `calc_ma120_backtest` 和 `result_ma120_summary`
- [ ] 相同参数重复执行幂等（先删后写）
- [ ] 行情数据复用 `raw_price_daily`，缺失时通过 `_ensure_data` 补拉

---

## Part B：MA120 策略 API 接口

### 新增文件

- `app/schemas/ma120.py` — 请求/响应 schema
- `app/api/ma120.py` — 路由（注册到 `main.py`，与 `/api/backtest/dca` 并列）

### 1. 创建 MA120 回测任务

```
POST /api/backtest/ma120
```

请求体：

```json
{
  "symbol": "510880",
  "start_date": "2023-01-01",
  "end_date": "2026-07-15",
  "capital_mode": "fixed",
  "principal": 100000,
  "monthly_amount": null,
  "splits": 10,
  "ma_period": 120,
  "buy_threshold": 0.985,
  "step": 0.01,
  "crash_threshold": 0.05,
  "crash_multiplier": 2,
  "sell_mode": "batch",
  "dividend_mode": "cash"
}
```

- `capital_mode` 不同时，`principal` / `monthly_amount` 的必填校验：
  - `fixed`：`principal` 必填，`monthly_amount` 忽略
  - `recurring`：`monthly_amount` 必填，`principal` 忽略
  - `hybrid`：两者均必填
- 自动检查并补拉行情数据（复用 `_ensure_data`）
- 返回 `task_id`

响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "task_id": "ma120_510880_20230101_20260715_fixed_..."
  }
}
```

### 2. 获取回测图表数据

```
GET /api/backtest/ma120/{task_id}/chart
```

```json
{
  "code": 0,
  "data": {
    "dates": ["2023-01-03", ...],
    "market_value": [...],
    "total_cost": [...],
    "pnl": [...],
    "return_rate": [...],
    "ma_values": [...],
    "close_prices": [...],
    "signals": ["hold", "buy", ...],
    "buy_points": [{"date": "2023-03-15", "price": 2.85, "amount": 10000}, ...],
    "sell_points": [{"date": "2023-06-20", "price": 3.12, "amount": 15000}, ...],
    "benchmark_returns": [...],
    "benchmark_name": "沪深300",
    "symbol_name": "红利ETF"
  }
}
```

### 3. 获取回测汇总指标

```
GET /api/backtest/ma120/{task_id}/summary
```

```json
{
  "code": 0,
  "data": {
    "total_invested": 100000.00,
    "final_value": 112350.50,
    "total_pnl": 12350.50,
    "total_return_rate": 12.35,
    "annualized_return": 8.20,
    "max_drawdown": 6.50,
    "buy_count": 8,
    "sell_count": 3,
    "dividend_total": 3200.00,
    "win_rate": 100.0,
    "symbol_name": "红利ETF"
  }
}
```

### 验收标准（API）

- [ ] 所有接口返回统一 `ApiResponse` 格式
- [ ] Swagger UI (`/docs`) 可正常查看和测试
- [ ] 参数校验完善（金额 > 0、日期合法、capital_mode 与参数匹配等）
- [ ] 图表数据格式可直接被 ECharts 消费
- [ ] 命中同参数已算结果时直接返回 task_id（与 DCA 一致的幂等逻辑）

---

## Part C：MA120 策略前端页面

### 新增文件

- `frontend/src/views/Ma120Backtest.vue` — 与 `Backtest.vue` 并列的新页面

### 1. 导航与布局

- 前端导航新增「MA120 策略回测」入口，与「定投回测」并列同级
- 页面布局、风格与定投回测页面保持一致（参数表单 + 指标卡片 + 图表区）

### 2. 参数表单

| 表单项 | 控件类型 | 说明 |
|--------|----------|------|
| 标的选择 | 搜索下拉 | 复用 `/api/symbols/search` |
| 起止日期 | 日期选择器 | 默认至今 |
| 资金模式 | 单选 | 固定本金 / 每月投入 / 混合 |
| 初始本金 | 数字输入 | fixed / hybrid 时显示 |
| 每月投入 | 数字输入 | recurring / hybrid 时显示 |
| 份数 | 数字输入 | 默认 10 |
| MA 周期 | 数字输入 | 默认 120 |
| 买入阈值 | 数字输入 | 默认 0.985 |
| 加仓步长 | 数字输入 | 默认 0.01 |
| 暴跌阈值/倍数 | 数字输入 | 默认 5% / 2x |
| 卖出方式 | 单选 | 分批 / 全部 / 半仓 |
| 分红处理 | 单选 | 现金 / 复投 |

- 资金模式切换时，表单动态显示/隐藏对应输入项
- 高级参数（暴跌阈值、分红处理）可折叠

### 3. 图表展示

**双轴组合图（与定投回测风格统一）：**

```
┌────────────────────────────────────────────┐
│            MA120 策略回测图表               │
│  ┌─ 左纵轴：金额（元）                      │
│  │  ── 市值曲线（主色）                     │
│  │  ── 成本曲线（灰色虚线）                 │
│  │  ── MA120 参考线（浅色虚线，可开关）      │
│  │  ▎ 盈亏柱状条（盈绿/亏红）               │
│  │  🔴 买入标记点                           │
│  │  🔵 卖出标记点                           │
│  │                                          │
│  ├─ 右纵轴：收益率（%）                     │
│  │  ── 收益率曲线（橙/金）                  │
│  └──────────────────────────────────────    │
│                横轴：时间                    │
└────────────────────────────────────────────┘
```

- 买入/卖出标记点用 ECharts `markPoint` 实现
- MA120 参考线可通过 legend 开关
- tooltip 联动，显示当日：价格、MA 值、偏离度、信号、持仓、市值、盈亏

### 4. 指标卡片

图表上方展示（与定投回测风格一致）：

- 累计投入
- 当前市值
- 累计收益（带颜色）
- 累计收益率（带颜色）
- 年化收益率
- 最大回撤
- 买入次数
- 卖出次数
- 胜率

### 验收标准（前端）

- [ ] 资金模式切换时表单平滑切换
- [ ] 图表正确渲染双轴 + 标记点 + MA 参考线
- [ ] tooltip 显示完整当日数据
- [ ] 指标卡片数据正确
- [ ] 与定投回测页面风格统一、导航并列

---

## 数据复用策略

| 数据 | 来源 | 复用方式 |
|------|------|----------|
| 标的日线行情 | `raw_price_daily` | 与 DCA 共用，`_ensure_data` 补拉 |
| MA 计算 | `_compute_ma()`（dca.py 已有） | 直接 import 复用 |
| 数据拉取 | `AkShareFetcher` | 同一 fetcher，同一套 `_ensure_data` 逻辑 |
| 基准（沪深300） | `raw_price_daily` symbol=510300 | 与 DCA chart 接口共用基准计算 |
| 标的名称 | `symbol_catalog.lookup_name()` | 直接复用 |

> **关键原则**：MA120 策略引擎不新建数据表存储行情，一切从 `raw_price_daily` 读取。
> MA 计算函数 `_compute_ma` 和数据保障函数 `_ensure_data` 从 DCA 模块提取为公共工具，两者共用。

---

## 开放问题（后续迭代）

- [ ] 分红复投（`dividend_mode=reinvest`）需要分红数据源，一期先支持 `cash` 模式
- [ ] 多标的对比（同一策略跑多个 ETF，横向比较）
- [ ] 参数寻优（自动搜索最优 buy_threshold / step 组合）
- [ ] 策略叠加（MA120 信号 + 定投节奏组合）
