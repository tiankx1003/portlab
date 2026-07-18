# 017 — ETF 资金流向图表（国家队动向观察）

## 目标

在「定投回测」「MA120 策略」之后新增第三个图表页：**ETF 资金流向观察台**，用于通过宽基 ETF 的资金动向观察主力 / 国家队的进出。

与现有两个回测页的**形态差异**（关键）：
- 回测页是「**计算工具**」（参数表单 + 跑回测 + 看结果）。
- 本页是「**数据看板**」（选标的 + 选区间 + 即时展示资金流），**不做策略计算、不产生 task_id、不写 summary 表**。

**三个观察维度**（同一页面，信号分层）：

| 信号 | 口径 | 数据源 | 强度 |
|------|------|--------|------|
| **ETF 份额变动** | 一级市场申赎 | `fund_etf_scale_s
| **主力 / 超大单资金流** | 二级市场成交单分类 | `stock_individual_fund_flow` | 中（主力资金，非特指国家队） |
| **北向资金净买额** | 全市场（沪深股通） | `stock_hsgt_hist_em` | 对照信号（北向也是主力之一，共振=强） |

**单标的观察**：像回测页一样选一个 ETF，前两个信号针对所选 ETF；北向资金是**全局对照**（与具体 ETF 无关，固定显示作为大盘资金背景）。

> **现实约束（影响设计）**：
> 1. `fund_etf_scale_sse` **仅上交所 ETF**（深交所 `fund_etf_scale_szse` 在 akshare 1.18.64 解析坏掉）。「份额变动」信号对深市 ETF 缺失，前端需做空态提示。所幸核心宽基（510300/510050/510500/510880 等）均在上交所，主力场景覆盖。
> 2. `stock_individual_fund_flow` 是单 ETF 逐个拉，无「国家队整体」聚合接口——本任务按「单标的」粒度规避此问题。
> 3. 一级市场申赎信号 = 「份额逐日变动」，需循环多日 `fund_etf_scale_sse` 才能拼出时间序列，单次请求 N 天 = N 次调用，**须落库缓存 + 补缺区间**避免重复拉取。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（复用 `DataFetcher` 抽象与 UPSERT 幂等范式）

> 与 003/007 无依赖：不读取 `result_*` 表，不调用回测引擎。
> 与 009（Tushare）无依赖：本任务资金流数据 akshare 独占，tushare 的资金流接口不纳入一期。

---

## Part A：后端

### 1. 数据模型

资金流数据与行情数据语义不同（份额 vs 价格 vs 成交单分类），**独立建表**，与 `raw_price_daily` / `raw_price_daily_tushare` 物理隔离（沿用 009 的隔离思路）。

#### 1.1 `raw_etf_flow_daily`（二级市场资金流，单 ETF 每日）

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | VARCHAR(32) | ETF 代码（PK） |
| trade_date | DATE | 交易日（PK） |
| main_net | DECIMAL(18,2) | 主力净流入额（元） |
| super_large_net | DECIMAL(18,2) | 超大单净流入额 |
| large_net | DECIMAL(18,2) | 大单净流入额 |
| medium_net | DECIMAL(18,2) | 中单净流入额 |
| small_net | DECIMAL(18,2) | 小单净流入额 |
| close | DECIMAL(14,4) | 当日收盘价（冗余，便于画价格线，避免 join price 表） |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |
| PRIMARY KEY (symbol, trade_date) | | UPSERT 幂等 |
| KEY idx_symbol_date (symbol, trade_date) | | |

> 来源：`stock_individual_fund_flow(stock, market)`，列映射 `主力净流入-净额→main_net`、`超大单净流入-净额→super_large_net` 等；`收盘价→close`。

#### 1.2 `raw_etf_share_daily`（一级市场份额，上交所 ETF 每日）

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | VARCHAR(32) | ETF 代码（PK） |
| trade_date | DATE | 日期（PK） |
| shares | DECIMAL(20,4) | 基金份额（万份） |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |
| PRIMARY KEY (symbol, trade_date) | | |

> 来源：`fund_etf_scale_sse(date='YYYYMMDD')` 返回全量上交所 ETF 某日份额，按 symbol 过滤落库。**Δ份额 = 当日 shares − 前一日 shares**，作为申赎净额（计算字段，不入库）。
> 深交所无此数据源；深市 ETF 此表无记录，前端空态。

#### 1.3 `raw_north_flow_daily`（北向资金，全局，每日）

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | DATE PK | 交易日 |
| channel | VARCHAR(8) | `north` / `sh` / `sz`（默认存聚合 `north`）（PK） |
| net_buy | DECIMAL(18,2) | 当日成交净买额（元） |
| buy_amount | DECIMAL(18,2) | 买入成交额 |
| sell_amount | DECIMAL(18,2) | 卖出成交额 |
| updated_at | TIMESTAMP | |
| PRIMARY KEY (trade_date, channel) | | |

> 来源：`stock_hsgt_hist_em(symbol='北向资金')`。北向是全局口径，与具体 ETF 无关，本表只存一份聚合序列。
> 注：2024 年后东财北向净买额列可能 NaN（报送规则变化），落库时 NaN 跳过，前端空态。

新建 `backend/app/models/etf_flow.py`、`etf_share.py`、`north_flow.py`，在 `models/__init__.py` 注册。

### 2. SQL Migration

- **新建 `mysql/init/05_etf_flow.sql`**：三张表 `CREATE TABLE IF NOT EXISTS`。
- **新建 `mysql/migrations/006_etf_flow.sql`**：同样三张表，供已部署库手动执行，文件头按惯例写明「fresh 安装已由 init/05 包含」。

### 3. 数据拉取

新建 `backend/app/services/fetcher/etf_flow_fetcher.py`（或并入 `akshare_fetcher.py` 作为额外方法）：

- `fetch_etf_flow(symbol, start, end) -> list[EtfFlowBar]`：调 `stock_individual_fund_flow(stock=symbol, market=_market_of(symbol))`，列映射后返回。`_market_of` 按代码首位判 sh/sz/bj（复用 `akshare_fetcher._to_tencent_symbol` 同源逻辑）。
- `fetch_etf_share(symbols, date) -> list[EtfShareBar]`：调 `fund_etf_scale_sse(date)`，按 `symbols` 过滤。一次调用拿全量，多 symbol 共享。
- `fetch_north_flow(start, end) -> list[NorthFlowBar]`：调 `stock_hsgt_hist_em('北向资金')`，过滤日期范围。

异常统一抛 `FetchError`（中文友好，含原始 message 便于排查积分/限频/接口变更）。

### 4. 数据保障（ensure 函数，复用 002 的幂等补缺范式）

新建 `backend/app/services/etf_data.py`，提供三个 `ensure_*` 函数（参照 `price_data.ensure_price_data`）：

- `ensure_etf_flow(db, symbol, start, end)`：查 `raw_etf_flow_daily` MIN/MAX/COUNT，仅补缺失区间，`upsert_etf_flow` 写回。
- `ensure_etf_share(db, symbol, start, end)`：查 `raw_etf_share_daily`，**对缺失的每个日期**逐日调 `fetch_etf_share`（因 `fund_etf_scale_sse` 按日返回）。缺失日多时开销大，前端给 loading 提示。
- `ensure_north_flow(db, start, end)`：北向数据全局共享，查 `raw_north_flow_daily` 补缺。

> **避免重复拉取**：所有 ensure 先查本地，已覆盖区间直接返回，仅对缺口发起请求；UPSERT 保证边界重叠幂等。与 `ensure_price_data` 同构。

`storage.py` 新增 `upsert_etf_flow` / `upsert_etf_share` / `upsert_north_flow`（参数化目标 model，沿用现有 upsert_bars 模式）。

### 5. Schema

新建 `backend/app/schemas/etf_flow.py`：

- `FlowQuery`：symbol、start_date、end_date
- `EtfFlowChartData`：dates[]、main_net[]、super_large_net[]、large_net[]、close[]、shares[]、share_delta[]（Δ份额，计算字段）、north_net[]（北向当日净买，对齐 dates）
- `EtfFlowSummary`：latest_date、today_main_net、main_net_5d_sum、latest_shares、share_delta_5d、north_today、is_sse（是否上交所，决定份额信号是否可用）

### 6. API 路由

新建 `backend/app/api/etf_flow.py`，路由前缀 `/api/etf-flow`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/etf-flow/data` | GET | 参数 `symbol, start_date, end_date`；先调三个 `ensure_*` 补数据，再聚合查询返回 chart + summary（合并一次返回） |

**业务规则：**
- **不产生 task_id、不写 summary 持久化表**（与回测本质区别）——每次请求即查即算即返回。
- `ensure_etf_share` 仅当 symbol 属上交所时调用；深交所跳过，`shares[]` 返回 null 数组，`is_sse=false`。
- 北向数据与 symbol 无关，直接按区间查 `raw_north_flow_daily`。
- 返回统一 `ApiResponse`。

> 图表与汇总合并为一个接口，因为本页无 task_id 中转，没必要拆两次请求。

### 7. 路由注册

`backend/app/main.py`：

```python
from .api import ..., etf_flow, ...
app.include_router(etf_flow.router, prefix="/api/etf-flow", tags=["etf-flow"])
```

### 验收标准（后端）

- [ ] 三张资金流表建成功（fresh 走 init/05，已部署走 migrations/006）
- [ ] `stock_individual_fund_flow` 拉取单 ETF 主力/超大单/大单/中单/小单净额，正确入库
- [ ] `fund_etf_scale_sse` 拉取上交所 ETF 份额，按 symbol 过滤入库；深交所 ETF 不报错、返回空
- [ ] `stock_hsgt_hist_em` 拉取北向资金净买额入库
- [ ] 三个 `ensure_*` 函数：区间已覆盖时不发请求；仅补缺口；UPSERT 幂等无重复行
- [ ] GET `/api/etf-flow/data` 返回 chart + summary，字段完整
- [ ] Δ份额（share_delta）正确计算（当日 − 前一日）
- [ ] 深交所 ETF 的份额相关字段返回 null / 空态，不报错
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. API 封装

`frontend/src/api/index.ts` 新增：

- `getEtfFlowData(params)` → GET `/api/etf-flow/data`（合并 chart + summary）
- 类型 `EtfFlowParams`、`EtfFlowChartData`、`EtfFlowSummary`

### 2. 路由与导航

- `router/index.ts` 新增 `{ path: '/etf-flow', name: 'etf-flow', component: EtfFlowView }`
- `App.vue` `nav-links` 新增 `<RouterLink to="/etf-flow">资金流向</RouterLink>`，排在「MA120 策略」之后。

### 3. 页面（`frontend/src/views/EtfFlowView.vue`）

**布局（与回测页壳子一致，但内容形态不同）：**

```
┌─────────────────────────────────────────────────────┐
│  ETF 资金流向                                        │
├─────────────────────────────────────────────────────┤
│  [标的搜索▼] [起始日期] [结束日期] [查询]           │  ← 控件栏（无参数表单）
├─────────────────────────────────────────────────────┤
│  [今日主力净流入] [近5日累计] [最新份额] [份额Δ5日] [北向今日] │  ← 指标卡片
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐    │
│  │         主力资金流 + 收盘价（双轴）          │    │  ← 主图 1
│  │  左轴: 主力/超大单净额(红绿堆叠柱, ±分色)    │    │
│  │  右轴: ETF 收盘价(折线)                      │    │
│  │  ⬆ 单日主力净流入超阈值(markPoint标注)       │    │
│  ├─────────────────────────────────────────────┤    │
│  │         份额变动（一级市场申赎）             │    │  ← 主图 2
│  │  折线: 基金份额(左轴)                        │    │
│  │  柱: Δ份额(右轴, 放大日=大额申赎)            │    │
│  │  ⬆ Δ份额异常日(markPoint)                   │    │
│  │  ⚠ 深市ETF此图显示「份额数据仅支持上交所」   │    │
│  ├─────────────────────────────────────────────┤    │
│  │         北向资金（对照）                     │    │  ← 主图 3
│  │  柱: 北向当日净买额(红绿)                    │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**控件栏**（非参数表单）：
- 标的搜索：复用 `/api/symbols/search`，默认填一个宽基（如 510300）。
- 起止日期：默认近 1 年。
- 查询按钮：触发 `getEtfFlowData`，loading 态禁用；份额补数慢时给「正在补拉份额数据，可能需数秒」提示。

### 4. 图表组件

新建 `frontend/src/components/EtfFlowChart.vue`（主图 1）、`EtfShareChart.vue`（主图 2）、`NorthFlowChart.vue`（主图 3）。**全部克隆 `Ma120Chart.vue` 的范式**：

- 生命周期、`setOption(opt, true)`、resize、dispose、watch(theme) 全照搬。
- `themeColors()` 主题调色板照搬。
- A 股色：`COLOR_UP='#ee6666'`（红，流入/涨）、`COLOR_DOWN='#3ba272'`（绿，流出/跌）——与回测页一致。
- tooltip `formatter`：按 `dataIndex` 从 `props.data` 取当日明细，HTML 内联色显示主力/超大单/份额/北向。
- dataZoom：inside + slider，照搬。
- `grid.right:120`（双轴留位）。

**主图 1（主力资金流）**：
- 左轴柱：主力净额按正负分两个 `stack:'flow'` 的 bar series（正→`COLOR_UP`，负→`COLOR_DOWN`），**复用 Ma120 盈亏柱的同款写法**。可选叠加超大单柱（另一个 stack 或切换 legend）。
- 右轴线：ETF 收盘价（`yAxisIndex:1`，`position:'right'`）。
- markPoint：单日主力净流入绝对值超阈值（如近 1 年 95 分位）的日子打 `⬆` 标。

**主图 2（份额变动）**：
- 左轴线：基金份额（累计绝对值，反映规模变化趋势）。
- 右轴柱：Δ份额（正=净申购/红，负=净赎回/绿），放大异常日。
- markPoint：Δ份额绝对值超阈值的日子打标（大额申赎=国家队进场痕迹）。
- **深市 ETF**：整图替换为居中提示「⚠ 份额数据仅支持上交所 ETF（数据源限制）」。

**主图 3（北向资金）**：
- 单柱：北向当日净买额（正红/负绿）。
- 与主图 1 时间轴对齐，可考虑后续做联动 dataZoom（一期各自独立）。

### 5. 指标卡片

用 `MetricCard.vue`，横排 5 张：
- 今日主力净流入（红/绿）
- 主力近 5 日累计（红/绿）
- 最新份额（万份）
- 份额 5 日变动（红/绿，仅上交所）
- 北向今日净买（红/绿）

### 6. 交互细节

- 切换标的/区间 → 重新查询；三图与卡片一次返回同步更新。
- legend 可开关各 series（主力/超大单/收盘价/份额/北向）。
- 三个图都有独立 dataZoom，一期不联动（联动列为开放问题）。
- 空数据态：份额图深市提示、北向 2024 后 NaN 提示「数据源暂无」。

### 验收标准（前端）

- [ ] 导航新增「资金流向」入口，与定投/MA120 并列
- [ ] 控件栏选标的 + 区间 + 查询，loading 态正常
- [ ] 主图 1：主力净额红绿堆叠柱 + 收盘价折线双轴，markPoint 标注异常日
- [ ] 主图 2：份额折线 + Δ份额柱双轴，异常日标注
- [ ] 主图 2 深市 ETF 显示「仅支持上交所」空态
- [ ] 主图 3：北向净买额红绿柱
- [ ] 指标卡片 5 项数据正确，红绿配色一致
- [ ] tooltip 显示当日完整明细
- [ ] legend 开关、dataZoom 缩放正常
- [ ] 明暗主题切换后三图样式正确
- [ ] 复用回测页 CSS 变量与组件（MetricCard / LegendHint）

---

## 数据复用与隔离策略

| 数据 | 表 | 来源 | 复用原则 |
|------|----|----|----------|
| 二级市场资金流 | `raw_etf_flow_daily`（新建） | `stock_individual_fund_flow` | ensure 补缺 + UPSERT 幂等 |
| 一级市场份额 | `raw_etf_share_daily`（新建） | `fund_etf_scale_sse` | 同上（按日逐次） |
| 北向资金 | `raw_north_flow_daily`（新建） | `stock_hsgt_hist_em` | 同上 |
| ETF 收盘价 | 冗余在 `raw_etf_flow_daily.close` | `stock_individual_fund_flow` 自带 | 避免与 `raw_price_daily` join |

> 三张资金流表与行情表完全隔离，互不污染。所有拉取走「先查本地→补缺口→UPSERT」幂等范式，从根本上避免重复拉取。

---

## 开放问题（后续迭代）

- [ ] **篮子聚合**：一期单标的；后续支持「国家队宽基篮子」多选求和，看整体进出场规模。
- [ ] **三图 dataZoom 联动**：一期各自独立；后续 connect 联动缩放。
- [ ] **异常日阈值自适应**：一期固定阈值或分位数；后续可让用户调。
- [ ] **份额信号补 SZSE**：等 akshare 修复 `fund_etf_scale_szse` 或换数据源（如交易所官方）后补深市。
- [ ] **每日定时拉取**：一期按需补拉；后续加定时任务，保证首页/本页打开即有最新数据（呼应 011 市场概览的实时性议题）。
- [ ] **Tushare 资金流**：一期纯 akshare；后续若 009 的 Tushare 通路提供 `moneyflow` 等接口，可作备选源（与 009 的 source 路由整合）。
- [ ] **国家队识别**：一期靠份额变动 + 主力流 + 北向三信号交叉判断；后续可引入「中央汇金持仓变动」等更直接信号（如有数据源）。
