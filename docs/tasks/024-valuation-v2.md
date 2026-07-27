# 024 — 估值看板 v2：PE 通道 + 多指数叠加 + 双源补强

## 目标

**估值看板 v2**：补强已交付的 016 简化 MVP，落实 016 原始设计文档规划但跳过的能力，并回应朋友反馈的四项核心需求。

**016 现状回顾（已交付 ☑，但是简化 MVP）**：
- 后端 `services/valuation.py`（83 行）+ 单端点 `GET /api/valuation?symbol=`，**仅 5 个指数硬编码**（沪深300/中证500/中证1000/上证50/创业板指），只调 `stock_index_pe_lg`（lg 源），**内存算、不落库**。
- 前端 `ValuationView.vue`（252 行），温度计仪表 + PE 历史折线（带「当前」markLine）+ 4 张 MetricCard。
- 016 原始设计文档承诺的：建表（`raw_index_valuation_daily`）、csindex 第二数据源、PB、股息率、ETF→指数映射（`resolve_index`）、`ensure` 补缺幂等、Schema 层、回看窗口、独立图表组件 —— **95% 未实现**。

**朋友反馈驱动的 4 项核心需求**：
1. **扩充指数到 12 个**（用户原话：上证50/沪深300/中证500/中证800/中证1000/中证2000/科创50/微盘/上证指数/深证成指/创业板指/科创板指）。
2. **时间窗口可选**：1/3/5/7/10 年（MVP 用全部历史，无窗口概念）。
3. **PE 估值通道**（参考同花顺）：5 条水平线把 PE 历史分成 4 个带，一眼看「现在落在贵还是便宜的区间」。
4. **多指数叠加比较**（参考 Wind 的「叠加」）：归一化第 1 天 = 1（或 1000），看哪个指数这段涨得多/估值修复快。

---

### 016 实现现状 vs 016 设计文档（偏离记录，诚实留档）

> 与 019→015 的「实现偏离记录」同模式，便于后续追溯。

| 016 设计文档承诺 | 016 实际实现 | 偏离 |
|------------------|-------------|------|
| `raw_index_valuation_daily` 独立建表 + ensure 补缺幂等 | 无表，内存现拉现算 | ❌ 未实现 |
| csindex 第二数据源（中证系指数 PE 历史 + 股息率快照） | 仅 lg 源 | ❌ 未实现 |
| `index_map` + ETF→指数映射（`resolve_index`） | 5 指数硬编码字典，无映射 | ❌ 未实现 |
| PB（lg 源完整 + 按源 NULL） | 未取 PB | ❌ 未实现 |
| 股息率（csindex 快照） | 未取 | ❌ 未实现 |
| `schemas/valuation.py` Schema 层 | 直接返回 dict | ❌ 未实现 |
| 回看窗口（5y/10y/成立）| 用全部历史 | ❌ 未实现 |
| 独立图表组件 `ValuationChart.vue`（克隆 Ma120） | 图表内联在 View | ❌ 未实现 |
| 25%/50%/75% 分位区间带 + 当前点 markPoint + 右轴收盘 | 仅「当前」水平线 | ❌ 未实现 |
| 12 指数覆盖（含中证800 等） | 仅 5 个 | ❌ 部分实现 |

**潜在 bug（本次顺带修复）**：`valuation.py:18` 把 `399006 创业板指` 映射到 `stock_index_pe_lg("创业板指")`，但 lg 的 `symbol_map` **没有「创业板指」这个 key**（只有「创业板50」399673）——切到创业板指会 `KeyError`。

---

## 12 指数支持矩阵（akshare 1.18.64 逐项实测）

> 本表是本任务一切承诺的基础，诚实标注数据可达性。实测依据：
> - lg 函数源码 `backend/.venv/.../akshare/stock_feature/stock_a_pe_and_pb.py`（`stock_index_pe_lg` L398、`stock_index_pb_lg` L511，`symbol_map` 固定 12 个中文 key）。
> - csindex 函数源码 `.../akshare/index/index_stock_zh_csindex.py`（覆盖「中证指数公司」发布的指数）。

| # | 指数 | 代码 | 数据源 | PE 历史 | PB | 股息率 | 本期状态 |
|---|------|------|--------|---------|----|----|----------|
| 1 | 上证50 | 000016 | lg | ✅ | ✅ | — | 可用（016 已有） |
| 2 | 沪深300 | 000300 | lg | ✅ | ✅ | — | 可用（016 已有） |
| 3 | 中证500 | 000905 | lg | ✅ | ✅ | — | 可用（016 已有） |
| 4 | 中证800 | 000906 | lg | ✅ | ✅ | — | 可用（**016 未配，本次新增**） |
| 5 | 中证1000 | 000852 | lg | ✅ | ✅ | — | 可用（016 已有） |
| 6 | 中证2000 | 932000 | csindex | ✅ | — | 快照 | 可用（**本次新增，需实测代码**） |
| 7 | 科创50 | 000688 | csindex | ✅ | — | 快照 | 可用（**本次新增**） |
| — | 科创板指 | 000688 | — | — | — | — | **= 科创50，不重复列出** |
| 8 | 上证指数（上证综指） | 000001 | — | ❌ | ❌ | ❌ | **不支持（灰显）** |
| 9 | 深证成指 | 399001 | — | ❌ | ❌ | ❌ | **不支持（灰显）** |
| 10 | 创业板指 | 399006 | — | ❌ | ❌ | ❌ | **不支持（灰显）**，修复 016 的 KeyError |
| 11 | 微盘 | — | — | ❌ | ❌ | ❌ | **不支持（灰显）** |

**实际可用 7 个**（5 lg + 中证2000 + 科创50）。

**为什么 4 个不支持**——akshare 双源皆无「指数级」PE/PB：
- **lg 源**只有 12 个固定宽基（见上），不含上证综指/深证成指/创业板指/科创50/中证2000/微盘。lg 另有「市场整体」PE（`stock_market_pe_lg`，参数 `{上证, 深证, 创业板, 科创版}`），但那是**整个交易所市场**的聚合 PE，成分股与具体指数不同，口径偏差大。
- **csindex 源**只覆盖「中证指数公司」发布的指数；上证综指（上交所）、深证成指（深交所）、创业板指（深交所/国证）**不在中证公司**，csindex 接口拿不到。
- **微盘股指数**双源皆无。

**本期立场（用户已拍板）：诚实标注不支持，不拿市场级 PE 凑数。** 理由：估值看板的核心价值是「这个指数现在贵不贵」，用成分不同的市场级 PE 近似会误导投资决策。4 个缺口指数在下拉中灰显禁选 + tooltip 说明原因。第三方源调研列为开放问题。

---

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（复用 `ensure_*` 补缺 + UPSERT 幂等范式；`FetchError` 中文友好）
- [016 — 估值温度计](./016-valuation-thermometer.md)（本任务是其迭代补强，不改 016 已交付代码）

> 与 021（股息率/DCF 估值回测）有反向依赖：021 的「股息率历史买入回测」强依赖本任务是否补出股息率历史序列；本期股息率仍仅 csindex 当日快照（无历史），021 走 PE 分位降级路径不受阻。

---

## Part A：后端

### 1. 数据模型（新建表，016 规划过但未建）

估值数据与行情/资金流语义独立，**独立建表**（沿用 009/012/016 隔离思路）。

#### 1.1 `raw_index_valuation_daily`（指数估值日序列）

| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | VARCHAR(16) | 指数代码（PK） |
| trade_date | DATE | 交易日（PK） |
| pe_ttm | DECIMAL(12,4) NULL | 滚动市盈率（核心，lg/csindex 统一存此列） |
| pb | DECIMAL(12,4) NULL | 市净率（仅 lg 源有，csindex 为 NULL） |
| dividend_yield | DECIMAL(8,4) NULL | 股息率(%)（仅 csindex 快照有，多数日 NULL） |
| source | VARCHAR(16) | lg / csindex（溯源） |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |
| PRIMARY KEY (index_code, trade_date) | | UPSERT 幂等 |
| KEY idx_index_date (index_code, trade_date) | | |

> NULL 字段语义：该数据源当天不提供该指标。前端按 NULL 做空态，不强求三指标齐全。

#### 1.2 `index_registry`（指数注册表，替代 016 硬编码字典）

| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | VARCHAR(16) | 指数代码（PK） |
| name_cn | VARCHAR(32) | 中文显示名 |
| lg_name | VARCHAR(32) NULL | lg 查询用中文名（仅 source_type=lg 用） |
| source_type | VARCHAR(16) | lg / csindex / none |
| supported | TINYINT(1) | 是否本期可用（0/1） |
| note | VARCHAR(128) NULL | 说明（不支持的原因等） |
| sort_order | INT | 下拉排序 |

预置 12 行（见上方支持矩阵），其中 7 个 `supported=1`、5 个 `supported=0`（含科创板指去重说明：note 写「与科创50(000688)同，不重复列出」）。

### 2. SQL Migration

- **`mysql/init/12_valuation_v2.sql`**：建两表 + 预置 `index_registry` 12 行。
- **`mysql/migrations/013_valuation_v2.sql`**：同样，已部署库用。

> **编号说明**：016 原设计承诺 `init/07_index_valuation.sql` + `migrations/008`，但 016 实际跳过了建表，且 07/008 编号后来被 event_dashboard 占用（`init/08_event_dashboard.sql`、`migrations/009_event_dashboard.sql` 等）。本任务接现有最大编号 init/11（portfolio）、migrations/012（portfolio）继续。

### 3. 数据拉取（新建 fetcher，016 规划过但未实现 csindex 分支）

新建 `backend/app/services/fetcher/valuation_fetcher.py`：

- `fetch_lg(lg_name) -> list[ValuationBar]`：调 `stock_index_pe_lg(symbol=lg_name)` + `stock_index_pb_lg(symbol=lg_name)`，按日期对齐合并，`滚动市盈率→pe_ttm`、`市净率→pb`。
  - 注意 lg 接口参数是**中文指数名**（lg_name 字段已存于 index_registry）。
- `fetch_csindex(index_code, start, end) -> list[ValuationBar]`：
  - `stock_zh_index_hist_csindex(symbol=index_code, start, end)` → `滚动市盈率→pe_ttm`，**过滤 NaN 行**。
  - 补当日 `stock_zh_index_value_csindex(symbol=index_code)` → `股息率1→dividend_yield`，仅写入最新一日。
- `fetch_valuation(index_code, source_type, lg_name, ...) -> list[ValuationBar]`：按 source_type 分发到上面两个。

异常统一抛 `FetchError`（中文友好，含原始 message）。csindex 的静态 xls 接口偶发不稳定，加重试（2 次，间隔 1s）。

> 不走 `DataFetcher` 抽象基类（与 016 MVP 一致——估值直接 `import akshare`），`_FETCHERS` 注册表不变。

### 4. 数据保障（ensure 函数，复用 002 范式）

新建 `backend/app/services/valuation_data.py`：

- `ensure_valuation(db, index_code, source_type, lg_name, start, end)`：
  - 查 `raw_index_valuation_daily` 的 MIN/MAX/COUNT，仅补缺失区间。
  - `upsert_valuation` 写回（UPSERT 幂等）。
- 股息率快照每次拉最新一日即可（覆盖式 UPSERT）。

> **避免重复拉取**：先查本地，已覆盖区间跳过；UPSERT 幂等。与 007/009/012 的 ensure 范式同构。

`storage.py` 新增 `upsert_valuation(db, bars)`（`ValuationBar` 为 dataclass，字段对齐表列）。

### 5. PE 通道计算（核心新逻辑，忠实用户指定算法）

新建 `backend/app/services/compute/valuation_metrics.py`（抽离 016 内联的 `percentile`，标准化为公共函数）：

```python
import statistics

def percentile_rank(value: float, series: list[float]) -> float | None:
    """value 在 series 中的历史分位（0~100，越大越贵）。
    从 016 valuation.py 内联逻辑迁出并标准化。"""
    valid = sorted(v for v in series if v is not None and v == v)  # 去 NULL/NaN
    if not valid:
        return None
    below = sum(1 for v in valid if v <= value)
    return round(below / len(valid) * 100, 2)

def pe_channel(pe_series: list[float]) -> dict:
    """5 条通道线（用户明确指定算法，非标准分位）：
    L1 = 周期最小值
    L3 = 中位数
    L2 = (L1 + L3) / 2  （最小值与中位数的平均值）
    L4 = (L3 + L5) / 2  （中位数与最大值的平均值）
    L5 = 周期最大值
    """
    valid = sorted(v for v in pe_series if v is not None and v == v)
    if not valid:
        return {}
    lo, hi, med = valid[0], valid[-1], statistics.median(valid)
    return {
        "l1_min": round(lo, 4),
        "l2_low": round((lo + med) / 2, 4),
        "l3_median": round(med, 4),
        "l4_high": round((med + hi) / 2, 4),
        "l5_max": round(hi, 4),
    }

def channel_position(current_pe: float, ch: dict) -> str:
    """当前 PE 落在 4 个带的哪一段，返回文字判断（参考同花顺高估/低估）。"""
    if not ch:
        return "—"
    if current_pe >= ch["l4_high"]:
        return "偏高估"
    if current_pe >= ch["l3_median"]:
        return "中高"
    if current_pe >= ch["l2_low"]:
        return "中低"
    return "偏低估"

def normalize_to_base(series: list[float | None], base: float = 1.0) -> list[float | None]:
    """多指数叠加归一化：第 1 天 = base（1 或 1000），其余按比例。
    缺失值（NULL）保持 None。"""
    out: list[float | None] = []
    first = next((v for v in series if v is not None), None)
    if first is None or first == 0:
        return [None] * len(series)
    for v in series:
        out.append(None if v is None else round(v / first * base, 4))
    return out
```

> **PE 通道算法说明**：用户原话「第 1 行=周期最小值，第 3 行=中位数，第 2 行=最小值与中位数的平均值，第 4 和第 5 行类似」。这**不是**标准的 25%/50%/75% 分位，是「min/median/max + 中点」的几何等分带。算法切换（vs 标准分位带）列为开放问题。

### 6. Schema（新建，016 规划过但未建）

新建 `backend/app/schemas/valuation.py`：

- `ValuationQuery`（单指数）：`symbol: str`、`lookback: Literal["1y","3y","5y","7y","10y","all"]`、`start_date: date | None`、`end_date: date | None`
- `SingleValuationData`：`index_code`、`name_cn`、`source_type`、`supported: bool`、`dates: list[str]`、`pe_ttm: list[float|None]`、`pb: list[float|None]`、`channel: dict`（l1..l5）、`current_pe`、`percentile`、`channel_position`、`current_pb`、`dividend_yield`、`pb_available: bool`、`dividend_available: bool`、`as_of: str`
- `OverlayQuery`（多指数）：`symbols: list[str]`、`lookback`、`base: Literal[1, 1000] = 1`
- `OverlayData`：`base`、`dates: list[str]`、`series: list[{index_code, name_cn, normalized: list[float|None]}]`
- `IndexItem`（下拉用）：`index_code`、`name_cn`、`source_type`、`supported: bool`、`note: str | None`

### 7. API 路由（扩展 016 单端点为多端点）

重写 `backend/app/api/valuation.py`，路由前缀 `/api/valuation`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/valuation/indices` | GET | 返回 `index_registry` 列表（12 个，含 supported/note，前端渲染下拉） |
| `/api/valuation/single` | GET | 参数 symbol、lookback、start_date、end_date；ensure 补缺 → 按窗口算通道+分位 → 返回 `SingleValuationData` |
| `/api/valuation/overlay` | GET | 参数 symbols[]、lookback、base；ensure 各指数 → 取共同日期区间 → 归一化 → 返回 `OverlayData` |

**业务规则：**
- **不产生 task_id、不写持久化 summary**（数据看板，与 012 同形态）——每次请求即查即算即返回，仅 `raw_index_valuation_daily` 缓存原始数据。
- `supported=false` 的指数：`/single` 返回 `supported=false` + note，不报错（前端据此灰显）。
- lookback 到 start_date 的换算：`1y`→今日回溯 365 天，依此类推；`all`→该指数入库最早日；start/end_date 显式传入时覆盖 lookback。
- overlay 取多指数的**共同交易日**做对齐归一化。
- **保留 016 旧端点 `GET /api/valuation?symbol=`**：内部转发到 `/single?lookback=all`，向后兼容（前端旧代码无感迁移）。
- 返回统一 `ApiResponse`。

### 8. 路由注册

`backend/app/main.py` 已 `include_router(valuation.router, prefix="/api/valuation")`（第 349 行），新增子端点无需改 include_router；仅 api/valuation.py 内部加路由函数。

### 验收标准（后端）

- [ ] `raw_index_valuation_daily` + `index_registry` 两表建成功（fresh 走 init/12，已部署走 migrations/013）
- [ ] `index_registry` 预置 12 行，7 supported=1、5 supported=0
- [ ] lg 源：上证50/沪深300/中证500/中证800/中证1000 的 PE+PB 完整日序列入库
- [ ] csindex 源：科创50/中证2000 的 PE 历史（过滤 NaN）+ 当日股息率快照入库
- [ ] `ensure_valuation`：已覆盖区间不发请求；仅补缺口；UPSERT 幂等
- [ ] `pe_channel` 5 线计算正确（L1=min, L2=(min+med)/2, L3=med, L4=(med+max)/2, L5=max）
- [ ] `percentile_rank` 正确（边界：空序列返回 None）
- [ ] `normalize_to_base` 第 1 天 = base，缺失值保持 None
- [ ] GET `/api/valuation/indices` 返回 12 项含 supported
- [ ] GET `/api/valuation/single` 返回 chart + summary，字段完整；lookback 切换通道/分位变化
- [ ] GET `/api/valuation/overlay` 多指数归一化对齐
- [ ] supported=false 指数返回 supported=false + note，不报错
- [ ] 旧端点 `GET /api/valuation?symbol=` 仍可用（向后兼容）
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. 独立图表组件（新建，016 规划过但图表内联了）

#### 1.1 `frontend/src/components/ValuationChannelChart.vue`（克隆 `Ma120Chart.vue` 范式）

**单指数 PE 通道图**，参考同花顺「估值通道/估值走势」：

- 主 series：PE-TTM 滚动历史折线（主色，左轴）。
- **PE 通道 5 条 markLine**（虚线，弱色，水平线）：
  - L5（max）— 标「极高」
  - L4 — 标「偏高」
  - L3（median）— 标「中位」，稍强色
  - L2 — 标「偏低」
  - L1（min）— 标「极低」
- **高估/低估色带**（参考同花顺，markArea 填充）：
  - L4–L5 区间：淡红填充（`rgba(238,102,102,0.10)`，高估区）
  - L1–L2 区间：淡绿填充（`rgba(59,162,114,0.10)`，低估区）
  - L2–L4：不填（中性区）
- **当前 PE markPoint**：最新一日 PE 大圆点 + 「现在」标签（高亮色）。
- **PB 折线**（右轴，仅 lg 源；csindex 源不渲染该 series）：`itemStyle.color=COLOR_PB`，虚线，宽 1.5。
- tooltip：日期、PE、分位%、通道位置（偏高估/中高/中低/偏低估）、PB（若可得）、股息率（若可得）。
- 生命周期 / `setOption(true)` / `resize` / `dispose` / `watch(theme)` / `themeColors()` 全照搬 Ma120Chart。
- dataZoom inside + slider。
- 主题色板：A 股惯例红涨绿跌不适用此处（PE 高=贵用红，PE 低=便宜用绿，与温度计配色一致）。

#### 1.2 `frontend/src/components/ValuationOverlayChart.vue`（多指数叠加，新组件）

**参考 Wind「叠加」**，多条归一化折线：

- 每个指数一条折线（themeColors 色板轮转），起点都对齐 = base（1 或 1000）。
- legend 可开关各指数（名称 + 代码）。
- tooltip：当日各指数归一化值 + 相对起点涨跌幅%（红涨绿跌着色）。
- 单轴（归一化值，左轴）。
- `watch(theme)` / resize / dispose / setOption(true) 同上。
- dataZoom inside + slider。

### 2. 页面改版（重写 `frontend/src/views/ValuationView.vue`，克隆 `Ma120Backtest.vue` 范式）

**布局：**

```
┌──────────────────────────────────────────────────────┐
│  估值看板                                              │
│  [视图切换: 单指数估值 | 多指数叠加]   ← 按钮组/tab    │
├──────────────────────────────────────────────────────┤
│  ▼ 单指数视图                                          │
│  ┌─────────────────────────────────────────────────┐ │
│  │ [指数下拉▼] [时间 5年▼] [起始日期] [结束] [查询]│ │  ← .form-card + .form-row + button.primary
│  └─────────────────────────────────────────────────┘ │
│  ┌ 当前PE  分位  通道位置  PB  股息率 ┐  ← MetricCard │
│  │ 12.30   35%   偏低估    1.21  —   │                │
│  └────────────────────────────────────┘               │
│  ┌─────────────────────────────────────────────┐     │
│  │      PE-TTM 折线 + 5 通道线 + 色带 + 当前点  │     │
│  │ ═══ L5 极高 ═══  (淡红: 高估区)              │     │
│  │ ── L4 偏高 ──                                │     │
│  │ ── L3 中位 ──                                │     │
│  │ ● PE 曲线（主色）                            │     │
│  │ ── L2 偏低 ──                                │     │
│  │ ═══ L1 极低 ═══  (淡绿: 低估区)              │     │
│  └─────────────────────────────────────────────┘     │
├──────────────────────────────────────────────────────┤
│  ▼ 多指数叠加视图                                      │
│  ┌─────────────────────────────────────────────────┐ │
│  │ ☑沪深300 ☑中证1000 ☐科创50 …   [基准 1▼] [查询]│ │
│  └─────────────────────────────────────────────────┘ │
│  ┌─────────────────────────────────────────────┐     │
│  │   归一化净值多线叠加（起点=1）                │     │
│  │   — 沪深300  — 中证1000  …                   │     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

**控件栏（复用 Ma120Backtest 的 `.form-card` + `.form-row` + `button.primary` 样式）**：
- 视图切换：两个按钮/tab（`单指数估值` / `多指数叠加`），`v-if` 切换下方区域。
- 单指数视图：
  - 指数下拉：从 `/api/valuation/indices` 动态加载；`supported=false` 的 **灰显 + disabled + title tooltip**（「akshare 无该指数的指数级 PE/PB 数据」）。
  - 时间下拉：`1年/3年/5年/7年/10年/成立以来`，默认 5 年；切换后通道与分位实时重算。
  - 起止日期：可选；显式输入时覆盖 lookback。
  - 查询按钮。
- 多指数视图：
  - 多选框列表（仅 supported=true 的 7 个可勾）；默认勾 2 个（沪深300 + 中证1000）。
  - 归一化基准下拉：`第1天=1` / `第1天=1000`，默认 1。
  - 查询按钮。

**MetricCard 区（复用 `MetricCard` 组件）**：
- 当前 PE（醒目）
- 历史分位（%，带偏低估/中低/中高/偏高估文字 + 配色：借用 016 `tempColor` 逻辑——<40 绿 / 40-60 灰 / 60-80 黄 / ≥80 红）
- 通道位置（偏高估/中高/中低/偏低估，配色同上）
- PB（lg 源显示数值；csindex 显示 `—`）
- 股息率（csindex 显示当前值 + 小字「仅当日快照」；lg 显示 `—`）
- 溯源行：`数据源：lg（乐咕乐股）/ csindex（中证指数公司）· 截至 YYYY-MM-DD`

**图表区**：`<ValuationChannelChart :data="..." />`（单指数）/ `<ValuationOverlayChart :data="..." />`（叠加）。

### 3. API 封装（扩展 `frontend/src/api/index.ts`）

新增：
- `getValuationIndices()` → GET `/api/valuation/indices`
- `getSingleValuation(params: SingleValuationParams)` → GET `/api/valuation/single`
- `getOverlayValuation(params: OverlayParams)` → GET `/api/valuation/overlay`
- 新增类型：`IndexItem`、`SingleValuationParams`、`SingleValuationData`、`OverlayParams`、`OverlayData`
- **保留旧 `getValuation(symbol)`**，加 `@deprecated` 注释（旧端点向后兼容，新代码不用）。

### 4. 空态与限制提示

- **不支持指数**：下拉灰显禁选 + tooltip「akshare 无该指数的指数级 PE/PB 数据（lg 无该宽基，csindex 不覆盖上交所/深交所发布指数）」。
- **PB 不可用**（csindex 源）：PB 卡显示 `—`，tooltip 不含 PB，可选小字「该指数无 PB 数据」。
- **股息率仅当日**（csindex）：股息率卡显示当前值 + 小字「仅当日快照，无历史分位」。
- **016 旧端点**：若前端仍有残留调用，平滑切到新端点。

### 5. 交互细节

- 切换时间窗口 → 重新查询，通道与分位实时变化（通道随窗口 min/median/max 变）。
- 切换指数 → 重新查询，PB/股息率可得性按源切换。
- 多指数叠加：勾选变化 / 基准切换 → 重新查询。
- legend 可开关 PE/PB/通道线/各叠加指数。
- 明暗主题切换后样式正确（含通道色带的淡红/淡绿）。

### 验收标准（前端）

- [ ] 视图切换（单指数/多指数叠加）可用，`v-if` 切换区域
- [ ] 指数下拉从 `/indices` 动态加载；5 个 supported=false 的灰显禁选 + tooltip
- [ ] 时间下拉 1/3/5/7/10 年/成立；切换后通道与分位更新
- [ ] PE 折线 + 5 通道线（L1-L5 带文字标签）+ 高估/低估色带 + 当前点 markPoint
- [ ] PB 折线（lg 源显示，csindex 不渲染）
- [ ] MetricCard：当前 PE / 分位 / 通道位置 / PB / 股息率，配色正确
- [ ] PB/股息率不可得时显示 `—`，不报错
- [ ] tooltip 显示完整当日明细（PE/分位/通道位置/PB/股息率）
- [ ] 多指数叠加归一化正确，起点对齐 = base；tooltip 显示涨跌幅
- [ ] 归一化基准切换（1 / 1000）
- [ ] 明暗主题切换后样式正确（含色带配色）
- [ ] 复用 Ma120Chart 范式与 CSS 变量（`.form-card` / `.form-row` / `button.primary` / `MetricCard`）

---

## 数据复用与隔离策略

| 数据 | 表 | 来源 | 复用原则 |
|------|----|----|----------|
| 指数估值（PE/PB/股息率） | `raw_index_valuation_daily`（新建） | lg + csindex | ensure 补缺 + UPSERT 幂等 |
| 指数注册 | `index_registry`（新建） | 预置 12 行 | 取代 016 硬编码 `_INDEX_NAMES` |
| 分位计算 | `percentile_rank`（迁出 016 内联） | 本地算 | 按回看窗口取子集 |
| PE 通道 | `pe_channel`（新增） | 本地算 | 按窗口 min/median/max |
| 多指数归一化 | `normalize_to_base`（新增） | 本地算 | 共同交易日对齐 |

> 估值表与行情/资金流表完全隔离。所有拉取走「先查本地→补缺口→UPSERT」幂等范式。不走 `DataFetcher` 抽象基类（与 016 MVP 一致，估值直接 import akshare）。

---

## 开放问题（后续迭代）

- [ ] **第三方源补 4 个缺口指数**：微盘 / 上证综指 / 深证成指 / 创业板指的指数级 PE/PB。候选：东方财富指数接口（`index_zh_a_hist` 有价格无 PE）、同花顺、国证指数官网。需调研口径一致性。
- [ ] **ETF→指数映射**：016 规划的 `resolve_index`（输入 ETF 自动解析到跟踪指数）。本期只做指数选择，ETF 映射列为后续。
- [ ] **股息率历史序列**：csindex 当日快照逐日累积，长期可拼出股息率历史（需每日定时拉取，呼应 014 限频治理与定时任务议题）。是 021（股息率/DCF 回测）的真正前置。
- [ ] **PB 覆盖扩展**：中证系指数若需 PB，可用 `index_stock_cons`（成分股）+ 个股 PB 加权聚合自建（重活，列为后续）。
- [ ] **PE 通道算法切换**：本期固定用户指定的 min/median/max 算法；后续可加「标准分位带（25/50/75%）」可选切换。
- [ ] **016 简化 MVP 旧端点的最终废弃**：本期保留 `GET /api/valuation?symbol=` 向后兼容；前端全量切到新端点后可移除旧端点。
