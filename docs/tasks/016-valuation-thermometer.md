# 016 — 估值温度计 / 估值分位看板

## 目标

新增第五个图表页：**估值温度计**。以指数 PE（滚动市盈率）的历史分位为核心，回答「这个指数现在贵不贵」——红利/ETF 投资的择时根本维度，补齐现有工具最明显的空白。

**与现有工具的互补关系**：
- 003/007/016 是「**价格/回撤**驱动择时」（看跌了多少决定买）。
- 本页是「**估值**驱动择时」（看贵不贵决定买）。
- 高估值 + 小回撤 比 低估值 + 大回撤 更危险——估值是更根本的安全边际信号。与 016（回撤买入）形成「估值定大方向、回撤定小买点」的组合拳。

**核心展示**：
- 选定指数的 **PE 滚动历史折线** + **历史分位区间带**（25%/50%/75% 分位参考线）。
- 当前 PE 在所选回看窗口（5年/10年/成立以来）的**历史分位**（0~100%，温度计式仪表盘或醒目大数）。
- 当日**股息率 / PB**（若可得）作为辅助读数徽章。
- 可选：估值定投信号（低估值多投、高估值少投，类 006 但以估值分位替代均线偏离）。

> **现实约束（决定性，影响整个交互模型）**——已逐项实测 akshare 1.18.64：
> 1. **ETF 级别无估值数据**。akshare 不发布 ETF 代码的 PE/PB/股息率。必须维护 **ETF → 跟踪指数**映射（如 512890→930955 中证红利低波动100、510880→000015 上证红利、510300→000300 沪深300）。用户选指数直接看；选 ETF 时自动解析到跟踪指数。
> 2. **数据源按指数类型分裂**（无统一接口）：
>    - **12 个宽基**（沪深300/上证50/中证500/中证1000/创业板50/深证红利/上证红利等）：乐咕乐股 `stock_index_pe_lg` + `stock_index_pb_lg`，PE+PB **完整日序列（2005 至今）**。
>    - **中证系指数**（中证红利 000922、红利低波 930955 等）：csindex 两接口拼——`stock_zh_index_hist_csindex` 给**历史 PE 序列**（TTM，早期 NaN 需过滤），`stock_zh_index_value_csindex` 给**当日快照**（含股息率两种口径）。
> 3. **股息率无历史序列**——仅 csindex 当日快照（~20 天）。**「股息率分位」做不了**，只能显示当前值。
> 4. **PB 对中证系指数不可用**（仅 12 宽基与个股有）。
> 5. **funddb 系列函数在 1.18.64 不存在**（网上教程误导），不可依赖。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（复用 `DataFetcher` 抽象与 UPSERT 幂等范式）
- [006 — 智能定投（均线定投策略）](./006-smart-dca.md)（估值定投信号可复用其动态扣款率思路）

> 与 016（回撤买入）无代码依赖，但概念互补；两者可同标的对照使用。

---

## Part A：后端

### 1. ETF → 跟踪指数映射表

新建 `app/services/index_map.py`（或配置表 `etf_index_map`），维护 ETF 代码到跟踪指数代码的映射：

| ETF | 跟踪指数 | 指数代码 | 数据源类型 |
|-----|----------|----------|------------|
| 510300 | 沪深300 | 000300 | lg |
| 510050 | 上证50 | 000016 | lg |
| 510500 | 中证500 | 000905 | lg |
| 512100 | 中证1000 | 000852 | lg |
| 159915 | 创业板50 | 399673 | lg |
| 510880 | 上证红利 | 000015 | lg |
| 512890 | 红利低波100 | 930955 | csindex |
| 515080 | 中证红利 | 000922 | csindex |
| 588000 | 科创50 | 000688 | csindex |

- 一期硬编码核心映射（~10 条），后续可改为配置表。
- 每个指数标注 `source_type`（`lg` / `csindex`），决定走哪个数据源。
- 提供 `resolve_index(etf_or_index_code) -> (index_code, name, source_type)`：输入 ETF 自动解析，输入指数直返。

### 2. 数据模型

估值数据与行情/资金流语义独立，**独立建表**（沿用 009/012 隔离思路）。

#### 2.1 `raw_index_valuation_daily`（指数估值日序列）

| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | VARCHAR(16) | 指数代码（PK） |
| trade_date | DATE | 交易日（PK） |
| pe_ttm | DECIMAL(12,4) NULL | 滚动市盈率（核心，两源统一存此列） |
| pb | DECIMAL(12,4) NULL | 市净率（仅 lg 源有） |
| dividend_yield | DECIMAL(8,4) NULL | 股息率(%)（仅 csindex 快照有，多数日为 NULL） |
| source | VARCHAR(16) | lg / csindex（溯源） |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |
| PRIMARY KEY (index_code, trade_date) | | UPSERT 幂等 |
| KEY idx_index_date (index_code, trade_date) | | |

> NULL 字段语义：该数据源当天不提供该指标。前端按 NULL 做空态，不强求三指标齐全。

### 3. SQL Migration

- **`mysql/init/07_index_valuation.sql`**：建表 + 预置 `etf_index_map`（若做成配置表）。
- **`mysql/migrations/008_index_valuation.sql`**：同样，已部署库用。

### 4. 数据拉取

新建 `backend/app/services/fetcher/valuation_fetcher.py`：

- `fetch_index_valuation_lg(index_name) -> list[ValuationBar]`：调 `stock_index_pe_lg(symbol=指数中文名)` + `stock_index_pb_lg(symbol=...)`，按日期对齐合并，pe→pe_ttm、pb→pb。
  - 注意 lg 接口参数是**中文指数名**（沪深300/上证50 等），需在 `index_map` 维护 `lg_name` 字段。
- `fetch_index_valuation_csindex(index_code, start, end) -> list[ValuationBar]`：
  - `stock_zh_index_hist_csindex(symbol=index_code, start, end)` → `滚动市盈率→pe_ttm`，**过滤 NaN 行**。
  - 补当日 `stock_zh_index_value_csindex(symbol=index_code)` → `股息率1→dividend_yield`，仅写入最新一日。
- `fetch_valuation(index_code, source_type, ...)`：按 source_type 分发到上面两个。

异常统一抛 `FetchError`（中文友好，含原始 message）。csindex 的静态 xls 接口偶发不稳定，加重试（2 次，间隔 1s）。

### 5. 数据保障（ensure 函数，复用 002 范式）

新建 `backend/app/services/valuation_data.py`：

- `ensure_valuation(db, index_code, start, end)`：查 `raw_index_valuation_daily` MIN/MAX/COUNT，仅补缺失区间，`upsert_valuation` 写回。
- 股息率快照每次拉最新一日即可（覆盖式 UPSERT）。

> **避免重复拉取**：先查本地，已覆盖区间跳过；UPSERT 幂等。

`storage.py` 新增 `upsert_valuation(db, bars, model=RawIndexValuationDaily)`。

### 6. 分位计算（核心新逻辑）

新建 `backend/app/services/compute/percentile.py`（或并入 valuation 服务）：

```python
def percentile_rank(value: float, series: list[float]) -> float:
    """value 在 series 中的百分位（0~100）。series 为历史 PE 序列（过滤 NULL/NaN）。"""
    valid = sorted(v for v in series if v is not None and v == v)  # 去 NaN
    if not valid:
        return float('nan')
    rank = sum(1 for v in valid if v <= value)
    return rank / len(valid) * 100
```

- 在 API 层按用户选的回看窗口（5y/10y/成立以来）取历史 PE 子集算当前 PE 的分位。
- 区间带：对该子集算 25%/50%/75% 分位（`numpy.percentile` 或自实现）。

### 7. Schema

新建 `backend/app/schemas/valuation.py`：

- `ValuationQuery`：symbol_or_index、lookback（`5y`/`10y`/`since_inception`）、start_date、end_date
- `ValuationChartData`：dates[]、pe_ttm[]、pb[]（可全 NULL）、pe_p25[]/pe_p50[]/pe_p75[]（滚动区间带，或固定值线）、index_close[]
- `ValuationSummary`：index_code、index_name、resolved_from_etf、current_pe、current_pb、current_dividend_yield、pe_percentile（0~100）、lookback、pe_min/pe_max（区间内）、source_type、pb_available、dividend_available

### 8. API 路由

新建 `backend/app/api/valuation.py`，路由前缀 `/api/valuation`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/valuation/data` | GET | 参数 symbol_or_index、lookback、start_date、end_date；resolve_index → ensure_valuation 补数据 → 算分位 → 返回 chart + summary（合并） |

**业务规则：**
- **不产生 task_id、不写持久化 summary**（数据看板，与 012 同形态）——每次请求即查即算即返回。
- 输入 ETF 自动解析到指数；解析不到的 ETF 返回 `ApiResponse.error("未找到该 ETF 的跟踪指数映射")`。
- pb/dividend 不可用时字段返回 null，`pb_available`/`dividend_available` 标 false，前端做空态。
- 返回统一 `ApiResponse`。

### 9. 路由注册

`backend/app/main.py`：

```python
from .api import ..., valuation, ...
app.include_router(valuation.router, prefix="/api/valuation", tags=["valuation"])
```

### 验收标准（后端）

- [ ] `raw_index_valuation_daily` 表建成功（fresh 走 init/07，已部署走 migrations/008）
- [ ] `resolve_index`：输入 ETF 返回跟踪指数；输入指数直返；未映射 ETF 返回错误
- [ ] lg 源：拉取 12 宽基的 PE+PB 完整日序列入库
- [ ] csindex 源：拉取中证系指数历史 PE（过滤 NaN）+ 当日股息率快照入库
- [ ] `ensure_valuation`：已覆盖区间不发请求；仅补缺口；UPSERT 幂等
- [ ] `percentile_rank` 正确计算（边界：空序列返回 NaN）
- [ ] GET `/api/valuation/data` 返回 chart + summary，字段完整
- [ ] PB/股息率不可用的指数，对应字段 null + `*_available=false`，不报错
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. API 封装

`frontend/src/api/index.ts` 新增：

- `getValuationData(params)` → GET `/api/valuation/data`
- 类型 `ValuationParams`、`ValuationChartData`、`ValuationSummary`

### 2. 路由与导航

- `router/index.ts` 新增 `{ path: '/valuation', name: 'valuation', component: ValuationView }`
- `App.vue` `nav-links` 新增 `<RouterLink to="/valuation">估值看板</RouterLink>`，排在「回撤买入」之后。

### 3. 页面（`frontend/src/views/ValuationView.vue`）

**布局：**

```
┌─────────────────────────────────────────────────────┐
│  估值温度计                                          │
│  [标的/指数搜索▼] [回看 5年▼] [区间] [查询]        │  ← 控件栏
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐  当前PE  分位  股息率  PB         │  ← 温度计 + 读数
│  │  温度计仪表 │   8.12   12%   4.97%   —          │
│  │   ▒▒▓▓░░░  │  ▎偏冷（适合定投）                 │
│  └─────────────┘                                    │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐    │
│  │         PE 历史折线 + 分位区间带            │    │  ← 主图
│  │  ┄┄ 75% 分位线 ┄┄                          │    │
│  │  ── 滚动PE（主色）  ┄ 50% 中位 ┄           │    │
│  │  ┄┄ 25% 分位线 ┄┄                          │    │
│  │  ● 当前点（高亮）                            │    │
│  │  右轴(可选): 指数收盘                        │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

**控件栏**：
- 标的/指数搜索：复用 `/api/symbols/search`，可输入 ETF 或指数代码；默认 512890（解析到 930955）。
- 回看窗口：下拉 5年/10年/成立以来，决定分位计算的历史区间。
- 起止日期 + 查询按钮。

**温度计 + 读数区**（卡片）：
- **温度计仪表**（SVG 半圆/条形）：当前 PE 分位映射到 0~100% 位置，颜色从冷（蓝/绿，低估值）到热（红，高估值）。
- **分位大数**：醒目显示当前分位%（如 12%），附文字判断（<30% 偏冷适合定投 / 30~70% 适中 / >70% 偏热谨慎）。
- 读数徽章：当前 PE、股息率（若可得）、PB（若可得）；不可得显示 `—`。
- 显示「解析自 ETF 512890 → 指数 930955 红利低波100」溯源行，让用户知道数据来自哪个指数。

### 4. 图表组件（`frontend/src/components/ValuationChart.vue`）

**克隆 `Ma120Chart.vue` 范式**：

- 主 series：PE 滚动历史折线（主色，左轴）。
- **分位区间带**：25%/50%/75% 三条 `markLine`（虚线，弱色），标「25% / 50% / 75%」。或用 ECharts `markArea` 填充 25~75% 为浅色带（「合理区间」）。
- **当前点高亮**：最新一日 PE 用 `markPoint`（大圆点 + 「现在」标签）。
- 右轴（可选）：指数收盘价折线（与 PE 对照，看「价格涨但 PE 没涨=盈利增长」的信号）。
- tooltip：日期、PE、分位、PB、股息率、指数收盘。
- 生命周期 / setOption(true) / resize / dispose / watch(theme) / themeColors() 全照搬。
- dataZoom inside + slider。
- A 股色复用，但温度计配色独立（冷热渐变，蓝→红）。

### 5. 空态与限制提示

- PB 不可用（中证系）：PB 徽章显示 `—`，tooltip 不含 PB，可选小字「该指数无 PB 数据」。
- 股息率仅当日：股息率徽章显示当前值，附小字「仅当日快照，无历史分位」。
- ETF 未映射：搜索后查询返回错误，前端提示「未找到该 ETF 的跟踪指数映射，请直接选指数」。

### 6. 交互细节

- 切换回看窗口（5y/10年/成立）→ 重新查询，分位与区间带实时变化。
- 切换标的 → 解析指数 → 重新查询。
- legend 可开关 PE/收盘价/区间带。

### 验收标准（前端）

- [ ] 导航新增「估值看板」入口
- [ ] 输入 ETF 自动解析到跟踪指数并显示溯源行
- [ ] 温度计仪表 + 分位大数 + 读数徽章正确展示
- [ ] 分位文字判断（偏冷/适中/偏热）正确
- [ ] PE 历史折线 + 25%/50%/75% 分位区间带
- [ ] 当前点高亮 markPoint
- [ ] PB/股息率不可得时徽章显示 `—`，不报错
- [ ] tooltip 显示完整当日明细
- [ ] 回看窗口切换后分位与区间带更新
- [ ] 明暗主题切换后样式正确（含温度计冷热配色）
- [ ] 复用 Ma120Chart 范式与 CSS 变量

---

## 数据复用与隔离策略

| 数据 | 表 | 来源 | 复用原则 |
|------|----|----|----------|
| 指数估值（PE/PB/股息率） | `raw_index_valuation_daily`（新建） | lg + csindex | ensure 补缺 + UPSERT 幂等 |
| ETF→指数映射 | `index_map`（硬编码/配置表） | 维护 | resolve_index 解析 |
| 分位计算 | `percentile_rank`（新增公共函数） | 本地算 | 按回看窗口取子集 |

> 估值表与行情/资金流表完全隔离。所有拉取走「先查本地→补缺口→UPSERT」幂等范式。

---

## 开放问题（后续迭代）

- [ ] **估值定投信号**：基于分位输出「低估多投、高估少投」的扣款率（类 006），与回测引擎结合，可演化出「估值版智能定投」独立回测。
- [ ] **多指数温度计总览**：首页或本页顶部并排显示多个核心指数的分位小卡（沪深300/红利/创业板当前多贵），一眼看全局。
- [ ] **PB 覆盖扩展**：中证系指数若需 PB，可用 `index_stock_cons_csindex`（成分股）+ `stock_value_em`（个股 PB）加权聚合自建（重活，列为后续）。
- [ ] **股息率历史**：csindex 当日快照逐日累积，长期可拼出股息率历史序列（需每日定时拉取，呼应 014 限频治理与定时任务议题）。
- [ ] **ETF→指数映射配置化**：一期硬编码，后续做管理后台或读取交易所公开映射。
- [ ] **与 016 组合**：同标的上「估值分位 + 回撤阈值」双信号叠加择时，估值定方向、回撤定买点。
