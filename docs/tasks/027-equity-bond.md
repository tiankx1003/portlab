# 027 — 股债比价看板

## 目标

**股债比价看板**：选择一个股指，用其 **EP（1/PE-TTM）或股息率** 除以 **十年期国债收益率**，得到「股债比价」曲线，叠加 **滚动均值 + ±1/±2/±3 标准差通道**，右轴叠加指数点位。对标用户提供的参考图（沪深300 股债比价 + 5 年滚动均值 + ±1/±2/±3σ 通道线 + 右轴指数）。

**核心价值**：股债比价（FED 模型）是经典的资产配置参考——比价越高（股票盈利收益率相对国债越占优）= 股票越便宜；通道带量化「当前比价在历史上贵还是便宜」。

---

### 用户已确认的设计决定（本任务的需求边界）

| 维度 | 决定 |
|------|------|
| 比价公式 | **EP/国债** 与 **股息率/国债** 双口径，前端可切换；默认 EP |
| 滚动窗口 | **3 / 5 / 10 年可选**，默认 5 年 |
| 支持指数 | 沪深300 / 中证500 / 上证50 等少数几个（复用 024 已支持的 `raw_index_valuation_daily` PE 数据） |
| 国债期限 | **固定十年期**（不做期限切换） |

---

## 数据源支持矩阵（akshare 1.18.64 实测）

> 本表是本任务一切承诺的基础，均经探索阶段实际调用验证。

### 指数 PE（复用 024，无需新拉取）

| 指数 | 代码 | PE 数据源 | 本期可用 |
|------|------|-----------|----------|
| 沪深300 | 000300 | lg（乐咕乐股） | ✅ |
| 中证500 | 000905 | lg | ✅ |
| 上证50 | 000016 | lg | ✅ |
| 中证800 | 000906 | lg | ✅（024 已有，按需纳入下拉） |
| 中证1000 | 000852 | lg | ✅（024 已有） |
| 中证2000 | 932000 | csindex | ✅（024 已有） |
| 科创50 | 000688 | csindex | ✅（024 已有） |

> 复用 024 的 `raw_index_valuation_daily` + `index_registry` + `ensure_valuation` 机制，**不重建 PE 数据通路**。本期下拉默认列出 000300/000905/000016 三个，可按需扩展到 024 全部 7 个。

### 十年期国债收益率（新建，核心新数据源）

| 函数 | 列 | 返回 | 实测结论 |
|------|----|------|----------|
| `bond_zh_us_rate(start_date=)` | `中国国债收益率10年`（float，单位 %，如 1.7141） | 全历史（实测 2024-01 起 687 行，起点可追溯到 1990） | ✅ **主源**，一次调用全历史，日期为 `datetime.date` |
| `bond_china_yield(start_date, end_date)` | `10年`（过滤 `曲线名称=='中债国债收益率曲线'`） | 单次最多约 1 年窗口 | ✅ **回退源**，分段拉取 |

- 项目当前**零代码**涉及国债收益率（grep `国债|bond|yield|czce|chinabond` 无相关命中），需全新建。
- 注意：`中国国债收益率10年` 有少量 NaN（实测 2.5 年区间约 45 个），需过滤。
- 收益率单位为**百分点**（1.71 表示 1.71%），EP 和股息率也用百分点口径，比值无量纲。

### 指数日线点位（右轴叠加用，新建）

| 函数 | 列 | 参数 | 实测结论 |
|------|----|----|----------|
| `stock_zh_index_daily` | `date`/`close` | 需 `sh`/`sz` 前缀（如 `sh000300`） | ✅ 实测沪深300/上证50/中证500/创业板指均可用 |

- 项目未拉过指数行情（`AkShareFetcher` 只拉个股 OHLCV），需新建。
- 指数代码 → 前缀映射：`3` 开头（399xxx 深证系）→ `sz`，其余（000xxx 上证系）→ `sh`。

### ⚠️ 股息率口径的数据约束（诚实标注）

- **EP 口径（1/PE）**：PE 为完整日序列（lg + csindex 双源），EP 口径**完整可靠**，是主口径。
- **股息率口径**：024 中股息率仅 csindex **当日快照**（稀疏，非完整历史序列），lg 源无股息率。
  - 后果：`股息率/国债` 历史曲线会**大量断点/缺失**。
  - 处理：股息率口径尽力而为——缺失处不画，前端明确提示「股息率历史稀疏（csindex 仅当日快照），曲线可能断续」。
  - 这是数据源硬限制，不是 bug；后续若补出股息率历史序列（见 024 开放问题）可平滑改善。

---

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（复用 `FetchError` 中文友好 + ensure 补缺 + UPSERT 幂等范式）
- [024 — 估值看板 v2](./024-valuation-v2.md)（**强依赖**：复用 `raw_index_valuation_daily` / `index_registry` / `ensure_valuation` / `read_series`；PE 数据不重建）

---

## Part A：后端

### 1. 数据模型（新建两表）

行情与估值语义独立，**独立建表**（沿用 002/009/024 隔离思路）。

#### 1.1 `raw_bond_yield_daily`（十年期国债收益率日序列）

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | DATE | 交易日（PK） |
| yield_10y | DECIMAL(6,3) NULL | 十年期国债收益率(%)（如 1.714） |
| source | VARCHAR(32) | `bond_zh_us_rate` / `bond_china_yield` |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |
| PRIMARY KEY (trade_date) | | UPSERT 幂等 |

#### 1.2 `raw_index_daily`（指数日线点位，右轴叠加用）

| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | VARCHAR(16) | 指数代码（PK） |
| trade_date | DATE | 交易日（PK） |
| close | DECIMAL(12,4) NULL | 收盘点位 |
| source | VARCHAR(32) | `akshare` |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |
| PRIMARY KEY (index_code, trade_date) | | UPSERT 幂等 |
| KEY idx_index_date (index_code, trade_date) | | |

> 不给 bond 建宽表存所有期限——用户已确认固定十年期，保持最小。`raw_price_daily` 是个股表，指数点位单独建表更清晰。

### 2. SQL Migration

- **`mysql/init/15_equity_bond.sql`**：fresh 安装建两表。
- **`mysql/migrations/016_equity_bond.sql`**：已部署库升级用，同两表。

> 编号接现有最大：init/14（etf_share）、migrations/015（etf_share）。

### 3. ORM 模型

新建 `backend/app/models/equity_bond.py`：
- `RawBondYieldDaily`（对应 `raw_bond_yield_daily`，克隆 `RawEtfShareDaily` 单主键风格）
- `RawIndexDaily`（对应 `raw_index_daily`，双主键 + 索引，克隆 `RawIndexValuationDaily` 风格）

### 4. 数据拉取（新建 fetcher）

新建 `backend/app/services/fetcher/equity_bond_fetcher.py`（不走 `DataFetcher` 抽象基类，与 024 估值 fetcher 一致——直接 `import akshare`）：

- `BondBar` dataclass：`trade_date, yield_10y, source`
- `IndexBar` dataclass：`index_code, trade_date, close, source`
- `fetch_bond_yield(start, end) -> list[BondBar]`：主源 `bond_zh_us_rate`（一次全量按区间过滤，去 NaN 行），失败回退 `bond_china_yield`（过滤曲线名称 + `10年` 列）。异常抛 `FetchError`。
- `fetch_index_close(index_code, start, end) -> list[IndexBar]`：`stock_zh_index_daily`（需 sh/sz 前缀，`_to_prefixed_symbol` 判定：3 开头→sz，其余→sh），全量后按区间过滤。
- 宽松 Decimal 转换复用 `valuation_fetcher._to_dec`。

### 5. 数据保障（ensure，复用 002/024 范式）

新建 `backend/app/services/equity_bond_data.py`：

- `ensure_bond_yield(db, start, end)`：查 `raw_bond_yield_daily` 的 MIN/MAX/COUNT，仅补缺失区间 → `upsert_bond_yield`（UPSERT 幂等）。端点假期容差复用 024 的 FRONT_TOL/BACK_TOL 思路。
- `ensure_index_close(db, index_code, start, end)`：同构，针对 `raw_index_daily`。
- **PE 数据复用 024 的 `ensure_valuation`**（不重写），按本任务窗口拉取补缺。

`storage.py` 新增：
- `upsert_bond_yield(db, bars: list[BondBar])`（克隆 `upsert_etf_shares` 单主键风格）
- `upsert_index_close(db, bars: list[IndexBar])`（克隆 `upsert_valuation` 双主键风格）

### 6. 滚动通道计算（核心新逻辑）

新建 `backend/app/services/compute/equity_bond_metrics.py`：

```python
import statistics
from datetime import date, timedelta

def rolling_channel(
    series: list[float | None],
    dates: list[date],
    window_years: int = 5,
) -> dict[str, list[float | None]]:
    """滚动均值 + ±1/±2/±3σ 通道。

    对每个非空 i，取 dates[i] 往前 window_years 年内的非空样本，算 mean 与 std，
    输出 7 条与 series 等长的序列：mean / p1,p2,p3（均值+Nσ）/ n1,n2,n3（均值-Nσ）。
    前段（窗口内样本不足 2 个，无法算 std）对应位置为 None。
    窗口按日期差截取子序列（timedelta(days=window_years*365.25)），而非固定交易日数。
    """
    ...

def channel_position(
    current_ratio, current_mean, current_p1, current_p2,
    current_n1, current_n2,
) -> str:
    """当前比价落在通道的哪一档（比价越高=股票越便宜）：
    极度昂贵(<-2σ) / 昂贵([-2σ,-1σ)) / 偏贵([-1σ,均值))
    / 中性([均值,+1σ)) / 偏便宜([+1σ,+2σ)) / 便宜(≥+2σ)
    """
    ...
```

> **与 024 `pe_channel` 的区别**：024 是全周期 min/median/max 静态 5 线；本任务是**逐日滚动**的均值±标准差带，每个交易日输出一组随时间漂移的通道值，还原 FED 模型的经典视图。这是真正的新算法。使用 `statistics.pstdev`（总体标准差）。

### 7. 编排（主函数）

`equity_bond_data.py` 新增：

```python
def build_equity_bond(
    db, index_code, metric, window, start_date, end_date,
) -> dict:
    """主编排：ensure 三类数据 → 按交易日对齐 → 算 ratio + 通道 → 组装返回。"""
    # 1. ensure：PE（复用 024 ensure_valuation）/ 国债 / 指数点位
    # 2. read_series：PE、国债、指数点位（按窗口）
    # 3. 按共同交易日对齐，算 ratio = EP/yield 或 dividend/yield
    #    - EP = 1/pe_ttm × 100（pe 用百分点口径，与 yield 单位一致）
    #    - 注意 yield、pe 为 None 的日子 ratio 为 None
    # 4. rolling_channel(ratio, dates, window_years) → 7 条通道线
    # 5. current_*（最后一日）、channel_position（当前档位）
    # 6. 组装 EquityBondData（含 metric/window/name_cn/as_of/warning）
```

> EP 单位说明：PE 是倍数（如 12.3），EP = 1/PE 是小数（如 0.0813 = 8.13%）；国债 yield 是百分点（如 1.71）。两者同以「%」为口径相除：ratio = (1/PE × 100) / yield，结果无量纲。

### 8. Schema

新建 `backend/app/schemas/equity_bond.py`：
- `Metric = Literal["ep", "dividend"]`
- `Window = Literal["3y", "5y", "10y"]`
- `EquityBondData`：`index_code`、`name_cn`、`metric`、`window`、`dates: list[str]`、`ratio: list[float|None]`、`mean/p1/p2/p3/n1/n2/n3: list[float|None]`、`index_close: list[float|None]`、`current_ratio`、`current_mean`、`current_position`、`as_of: str`、`warning: str | None`
- `IndexItem`：复用 024 或轻量重定义（`index_code`、`name_cn`）

### 9. API 路由

新建 `backend/app/api/equity_bond.py`，路由前缀 `/api/equity-bond`：

| 接口 | 方法 | 参数 | 说明 |
|------|------|------|------|
| `/api/equity-bond/indices` | GET | — | 返回本看板支持的指数清单（从 `index_registry` 取 `supported=1`，按白名单过滤） |
| `/api/equity-bond/single` | GET | `index_code`、`metric`（ep/dividend）、`window`（3y/5y/10y）、`start_date?`、`end_date?` | 主接口：返回 `EquityBondData` |

**业务规则：**
- 不产生 task_id、不写持久化 summary（数据看板，与 016/024 同形态）——每次请求即查即算即返回，仅 `raw_bond_yield_daily` / `raw_index_daily` 缓存原始数据。
- `metric=dividend` 且该指数无股息率历史时：返回数据 + `warning` 字段提示「股息率历史稀疏」，不报错。
- 窗口换算：`3y`→回溯 3 年，依此类推；显式 start/end_date 传入时覆盖窗口。注意：滚动通道需要「窗口前再前推一个窗口」的数据（5 年滚动需 10 年数据起），拉取区间自动前推。
- 返回统一 `ApiResponse`。

### 10. 路由注册 + 自愈建表

- `backend/app/main.py`：`app.include_router(equity_bond.router, prefix="/api/equity-bond", tags=["equity-bond"])`
- 自愈建表：参照 024 `_ensure_valuation_tables`（main.py:273），新增 `_ensure_equity_bond_tables`（`RawBondYieldDaily` / `RawIndexDaily` 建表）。

### 验收标准（后端）

- [ ] `raw_bond_yield_daily` + `raw_index_daily` 两表建成功（fresh 走 init/15，已部署走 migrations/016）
- [ ] `fetch_bond_yield`：主源 `bond_zh_us_rate` 返回完整序列，NaN 行过滤；失败回退 `bond_china_yield`
- [ ] `fetch_index_close`：沪深300/上证50/中证500 收盘点位完整入库
- [ ] `ensure_bond_yield` / `ensure_index_close`：已覆盖区间不发请求；仅补缺口；UPSERT 幂等
- [ ] `rolling_channel`：逐日输出 mean + ±1/±2/±3σ 共 7 条等长序列；前段不足窗口处为 None
- [ ] `channel_position`：6 档判断正确（极度昂贵/昂贵/偏贵/中性/偏便宜/便宜）
- [ ] EP 口径：ratio = (1/PE × 100) / yield，完整无断点
- [ ] 股息率口径：断点处 ratio 为 None，warning 透出
- [ ] GET `/api/equity-bond/single?index_code=000300&metric=ep&window=5y` 返回完整 ratio + 7 通道线 + 指数点位
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. 图表组件（克隆 `ValuationChannelChart.vue`）

新建 `frontend/src/components/EquityBondChart.vue`：

- **左轴**：股债比价（主曲线，红色，参照图片）+ 滚动均值（灰色实线）+ ±1/±2/±3σ（6 条 markLine 虚线，颜色由近到远渐淡，参照图片配色）
- **右轴**：指数点位（浅棕色实线，`splitLine:{show:false}`，`position:'right'`）
- **markPoint**：当前比价点（醒目圆点）
- **tooltip**：日期 / 比价值 / 均值 / 落在几σ档位 / 指数点位
- **±σ 通道带**（可选 markArea）：±1σ 区间淡色填充
- 生命周期 / `setOption(true)` / `resize` / `dispose` / `watch(theme)` / `themeColors()` 全照搬 `ValuationChannelChart`
- dataZoom inside + slider
- 配色：比价高（股票便宜）用绿色系，低（贵）用红色系（与 FED 模型直觉一致，比价越高越值得买）

### 2. 页面（克隆 `ValuationView.vue` 范式）

新建 `frontend/src/views/EquityBondView.vue`：

```
┌──────────────────────────────────────────────────────┐
│  股债比价                                              │
│  [指数 沪深300▼] [口径 EP▼] [窗口 5年▼] [起] [止] [查询]│
├──────────────────────────────────────────────────────┤
│  ┌ 当前比价  当前均值  ±1σ区间  当前档位  数据截至 ┐  │
│  │  3.21      2.85     2.1~3.6   偏便宜   07-31   │  │  ← MetricCard
│  └────────────────────────────────────────────────┘  │
│  ⚠ 股息率口径下显示：「股息率历史稀疏，曲线可能断续」   │
│  ┌─────────────────────────────────────────────┐     │
│  │  ═══ +3σ ═══                                │     │
│  │  ═══ +2σ ═══                                │     │
│  │  ── +1σ ──                                 │     │
│  │  ── 均值 ──                                 │     │
│  │  ● 比价曲线（红，左轴）                      │     │
│  │  ── -1σ ──                                 │     │
│  │  ═══ -2σ ═══                                │     │
│  │  ═══ -3σ ═══                                │     │
│  │     指数点位（浅棕，右轴）                   │     │
│  └─────────────────────────────────────────────┘     │
└──────────────────────────────────────────────────────┘
```

**控件栏**（复用 `ValuationView` 的 `.form-card` + `.form-row` + `button.primary`）：
- 指数下拉：从 `/api/equity-bond/indices` 加载，默认沪深300
- 口径下拉：EP / 股息率，默认 EP
- 窗口下拉：3 年 / 5 年 / 10 年，默认 5 年
- 起止日期：可选，覆盖窗口
- 查询按钮

**MetricCard 行**：当前比价、当前均值、±1σ 区间、当前档位、数据截止日。

**提示条**：股息率口径下显示「股息率历史稀疏（csindex 仅当日快照），曲线可能断续」。

### 3. API 封装

`frontend/src/api/index.ts` 新增：
- `EquityBondData` / `EquityBondSingleParams` / `EquityBondIndexItem` 类型
- `getEquityBondIndices()` → GET `/api/equity-bond/indices`
- `getEquityBondSingle(params)` → GET `/api/equity-bond/single`

### 4. 路由 + 导航

- `frontend/src/router/index.ts`：加 `{ path: '/equity-bond', name: 'equity-bond', component: EquityBondView }`
- `frontend/src/App.vue:22-32`：导航栏「估值」后加 `<RouterLink to="/equity-bond">股债比价</RouterLink>`

### 验收标准（前端）

- [ ] `/equity-bond` 页面渲染：控件栏 + MetricCard 行 + 图表
- [ ] 图表：主曲线 + 均值 + ±1/±2/±3σ（6 条）+ 右轴指数点位，与参考图效果一致
- [ ] 切换 EP/股息率、3/5/10 年窗口、不同指数均能正确重算
- [ ] 股息率口径下显示缺失提示条
- [ ] tooltip 显示日期/比价/均值/档位/指数点位
- [ ] 明暗主题切换后样式正确
- [ ] dataZoom 缩放正常
- [ ] 复用 ValuationChannelChart 范式与 CSS 变量
- [ ] `npm run build`（vue-tsc）通过

---

## 数据复用与隔离策略

| 数据 | 表 | 来源 | 复用原则 |
|------|----|----|----------|
| 指数 PE/PB | `raw_index_valuation_daily`（024 建） | lg + csindex | **复用 024** `ensure_valuation` / `read_series`，不重建 |
| 指数注册 | `index_registry`（024 建） | 预置 | **复用 024**，白名单过滤 |
| 十年期国债收益率 | `raw_bond_yield_daily`（新建） | bond_zh_us_rate + bond_china_yield 回退 | ensure 补缺 + UPSERT 幂等 |
| 指数日线点位 | `raw_index_daily`（新建） | stock_zh_index_daily | ensure 补缺 + UPSERT 幂等 |
| 滚动通道 | `rolling_channel`（新增） | 本地算 | 逐日窗口统计 |
| 档位判断 | `channel_position`（新增） | 本地算 | 基于 ±Nσ |

> 股债比价表与估值/行情表完全隔离。所有拉取走「先查本地→补缺口→UPSERT」幂等范式。不走 `DataFetcher` 抽象基类（与 024 一致，直接 import akshare）。

---

## 开放问题（后续迭代）

- [ ] **股息率历史序列**：当前 csindex 仅当日快照，导致「股息率/国债」口径断续。补全方案见 024 开放问题（每日定时拉取累积）。是 021（股息率/DCF 回测）的共同前置。
- [ ] **国债期限切换**：本期固定十年期；`bond_zh_us_rate` 一次返回 2/5/10/30 年四列，后续可加期限下拉。
- [ ] **多指数股债比价叠加**：本期单指数；后续可加多指数比价归一化叠加（克隆 024 overlay 思路）。
- [ ] **创业板指等缺口指数**：024 已验证双源皆无指数级 PE，本期不纳入；待第三方源补齐（见 024 开放问题）。
