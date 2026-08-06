# 032 — 估值与信号看板（估值重构 + 三层共振）

## 目标

**一句话**：用一个看板回答「现在市场处于什么状态，我该不该动」——按设计文档 `docs/refer/估值与信号看板设计.md` 落地完整的「三层共振」信号体系，并把现有零散的估值/股债比价功能整合为统一入口。

### 三层结构（忠实设计文档）

| 层 | 回答的问题 | 包含指标 |
|----|-----------|---------|
| **第一层：技术 + 估值** | 这个标的现在便宜吗？趋势如何？ | MA120 偏离、当前回撤、PE 分位、PB 分位、股息率、股债比价 |
| **第二层：大类资产估值** | 股市整体贵不贵？相对债券值不值？ | 股债收益比、沪深300/中证全指全收益 vs 5 年均线、创业板/上证比值、基金发行热度 |
| **第三层：资金 + 宏观** | 聪明钱往哪走？宏观松紧？ | 社融、M1/M2、PMI、PPI、融资融券余额、ETF 净流入、北向资金 |

### 核心理念（设计文档原文）

> 三层全绿 = 历史底部区域特征；三层全红 = 历史顶部特征；其余 95% 时间 = 不动，继续定投。
> 体温计，不是交易台——只呈现状态，不输出买卖指令。

---

## 用户已确认的设计决定（本任务的需求边界）

| 维度 | 决定 |
|------|------|
| 范围 | **完整三层共振**，含资金/宏观（依赖 Tushare 5000 积分） |
| 布局 | **单页长滚动**，三大模块纵向铺开 + 顶部信号汇总区 |
| 信号汇总 | **三层各自汇总灯 + 共振判断矩阵**（全绿=底部等） |
| 数据源策略 | **AkShare 为主 + Tushare 补强资金/宏观**；Tushare 已开通 5000 积分 |
| 硬伤处理 | 股息率历史序列/红利指数 PB **降级显示**（AkShare+Tushare 都无历史序列）；红利指数 **PE 可用**（csindex 2018 起），初版漏配 registry 已由 migration/017 补注册 |
| 股债比价 | **并入本看板**（吸收 027，不再独立实现） |
| 与现有页 | **重构 `/valuation`**，下线 016 旧代码 |

---

## 数据源支持矩阵（akshare 1.18.64 + Tushare Pro 实测）

> 本表是本任务一切承诺的基础。AkShare 部分逐项实测；Tushare 部分依据官方文档（doc_id 标注）。

### 第一层：技术 + 估值

| 指标 | 主数据源 | Tushare 补强 | 实测结论 |
|------|---------|-------------|---------|
| PE 分位 | AkShare `stock_index_pe_lg`（lg）/ `stock_zh_index_hist_csindex`（csindex） | — | ✅ 宽基完整序列（2005 起）；红利指数（930955/000922/000015）csindex 有「滚动市盈率」完整序列（实测 **2018 起**），fetcher `fetch_csindex` 已支持。⚠️ **须在 `index_registry` 注册（source_type=csindex, supported=1）后才点亮**——初版 032 漏配，导致选 512890/515080/513920/510880 时 PE 走 else 灰显；migration/017 已补注册 3 个红利指数。 |
| PB 分位 | AkShare `stock_index_pb_lg`（仅 lg 5 宽基） | — | ⚠️ **仅 5 宽基有 PB 历史**；红利/中证系指数无 PB（csindex hist/value 均无 PB 列）→ 降级灰显（硬伤二，数据源真缺，与 PE 灰显原因不同） |
| 股息率 | AkShare `stock_zh_index_value_csindex`（csindex 当日快照） | Tushare `index_dailybasic` **无股息率字段** | ❌ **无历史序列**（仅~20天快照）→ 只显示当前值，标「快照」，不算分位不赋灯。**注：该快照仅在指数已注册（supported=1）时展示；未注册时连快照值都不显示。** |
| MA120 偏离 | 本地算（需指数点位） | — | ✅ 复用 024 的 `compute_ma`，需指数点位表 |
| 当前回撤 | 本地算 | — | ✅ 复用 024 的 `max_drawdown` |
| 股债比价 | 国债 `bond_zh_us_rate` + 指数 PE | — | ✅ 吸收 027 设计，EP 口径完整 |

### 第二层：大类资产估值

| 指标 | 数据源 | Tushare | 实测结论 |
|------|--------|---------|---------|
| 十年期国债 | AkShare `bond_zh_us_rate`（主）/ `bond_china_yield`（回退） | — | ✅ 全历史（1990 起），单位百分点 |
| 指数点位（价格） | AkShare `stock_zh_index_daily`（sh/sz 前缀） | — | ✅ 沪深300/上证50/创业板指/上证指数均可用 |
| **全收益指数** | AkShare `stock_zh_index_hist_csindex`（**H 代码，须显式传日期**） | Tushare `index_daily`（H代码待实测） | ✅ **实测可用**：H00300 沪深300全收益、H00985 中证全指全收益、H00922 中证红利全收益。**关键：必须显式传 start/end_date**，否则默认停在 2024-06 |
| 创业板/上证比值 | 指数点位表（价格） | — | ✅ 两价格指数相除 |
| 基金发行规模 | — | Tushare `fund_basic.issue_size`（**120 积分**） | ✅ 按 `fund_type` 筛股基/偏股混合，按 `found_date` 月度聚合 |

### 第三层：资金 + 宏观（全部走 Tushare，5000 积分覆盖）

| 指标 | Tushare 接口 | 积分 | 字段 | 频率 |
|------|-------------|------|------|------|
| 社融增速 | `sf_month` (doc_id=310) | 2000 | `stk_endval` 存量→算同比 | 月频 |
| M1/M2 剪刀差 | `cn_m` (doc_id=242) | **600** | `m1_yoy` / `m2_yoy` 做差 | 月频 |
| PMI | `cn_pmi` (doc_id=325) | **5000** | `制造业PMI` | 月频 |
| PPI | `cn_ppi` (doc_id=245) | **600** | `ppi_yoy` 当月同比 | 月频 |
| 融资融券余额 | `margin` (doc_id=58) | 2000 | `rzye` 融资余额 / `rqye` 融券余额 | 日频 |
| ETF 净流入 | `fund_share`（已用）+ `fund_nav` | 2000 | 份额变动 × 净值 | 日频 |
| 北向资金 | `moneyflow_hsgt`（已用，017） | 2000 | `north_money` | 日频（⚠️ 2024-08 后口径调整为总额披露，换源不解决） |

> **积分门槛结论**：5000 积分覆盖全部含 PMI；若降级到 2000 积分则放弃 PMI（或改国家统计局网页）。本任务按 5000 设计。

### ⚠️ 数据源硬伤 vs 注册缺口（区分两类降级）

**A. 真硬伤（AkShare + Tushare 都无法解决，需第三方源）**

| 硬伤 | 原因 | 处理 |
|------|------|------|
| **股息率历史分位** | AkShare 仅~20天快照；Tushare `index_dailybasic` 无股息率字段，`daily_basic` 只到个股级 | 只显示当前值 + 「快照」标注，**不算分位、不赋信号灯** |
| **红利类指数 PB** | AkShare lg 无红利指数；csindex hist/value 均无 PB 列；Tushare `index_dailybasic` 只覆盖 6 宽基 | 灰显「无数据」，不赋灯 |

> 这两个缺口的彻底解决需引入第三方估值源（理杏仁 API、蛋卷、中证官网 FactSheet），列为本任务开放问题，不在 032 内实现。

**B. 注册缺口（数据源可用，仅未在 `index_registry` 预置——非硬伤）**

| 缺口 | 实际数据源 | 处理 |
|------|-----------|------|
| **红利指数 PE 分位**（产品层曾被误灰显） | csindex hist「滚动市盈率」完整序列（930955/000922/000015 实测 2018 起），fetcher `fetch_csindex` 已支持 | ✅ **已修**：migration/017 补注册 3 个红利指数（source_type=csindex, supported=1）。注册后 PE 分位/股债比价点亮，股息率显示快照值。**PB 仍灰**（属 A 类硬伤） |

> 初版 032 的 `_ETF_INDEX_MAP` 把 512890/515080/513920/510880 映射到 930955/000922/000015，但 024 预置的 12 行 registry 未含这 3 个红利指数，导致 `build_target_signals` 走 else 分支，PE/股息率/股债比价被误灰显（与数据源无关，纯注册漏配）。

---

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（`FetchError` + ensure 补缺 + UPSERT 幂等范式）
- [009 — Tushare 数据源扩展](./009-tushare-data-source.md)（Tushare token + `_resolve_token` + 013 限频治理 `_throttle`/`_split_ranges`/重试）
- [013 — Tushare 限频治理](./013-tushare-rate-limit.md)（分段拉取、节流、积分不足提示）
- [016 — 估值温度计](./016-valuation-thermometer.md)（**下线旧代码** `services/valuation.py` + `/api/valuation` 空端点）
- [024 — 估值看板 v2](./024-valuation-v2.md)（**复用** `raw_index_valuation_daily` / `index_registry` / `ensure_valuation` / `read_series` / `pe_channel` / `percentile_rank` / `valuation_fetcher`）
- [027 — 股债比价看板](./027-equity-bond.md)（**吸收**：国债表 + 指数点位表 + `rolling_channel` + 股债比价图，027 不再独立实现）
- [017 — ETF 资金流向图表](./017-etf-fund-flow.md)（复用 `pro.fund_share` / `pro.moneyflow_hsgt` 调用范式）

---

## Part A：后端

### 1. 数据模型（新建表）

估值数据复用 024（不重建）。本任务新建以下表：

#### 1.1 `raw_bond_yield_daily`（十年期国债，吸收 027）

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | DATE | 交易日（PK） |
| yield_10y | DECIMAL(6,3) NULL | 十年期国债收益率(%) |
| source | VARCHAR(32) | `bond_zh_us_rate` / `bond_china_yield` |
| updated_at | TIMESTAMP | `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

#### 1.2 `raw_index_daily`（指数日线点位，吸收 027 + 扩展全收益）

| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | VARCHAR(16) | 指数代码（PK），含 H 全收益代码 |
| trade_date | DATE | 交易日（PK） |
| close | DECIMAL(12,4) NULL | 收盘点位 |
| index_type | VARCHAR(16) | `price`（价格）/ `total_return`（全收益） |
| source | VARCHAR(32) | `akshare_daily` / `akshare_csindex` |
| updated_at | TIMESTAMP | 同上 |
| PRIMARY KEY (index_code, trade_date) + KEY idx_index_date | | |

> 比 027 设计多一个 `index_type` 字段，区分价格指数（`stock_zh_index_daily`）与全收益指数（`stock_zh_index_hist_csindex` H 代码），同表共存。

#### 1.3 `raw_macro_indicator`（宏观指标月/日序列，Tushare）

| 字段 | 类型 | 说明 |
|------|------|------|
| indicator | VARCHAR(32) | 指标键（PK），如 `sf_yoy`/`m1_yoy`/`m2_yoy`/`ppi_yoy`/`pmi` |
| ref_date | DATE | 数据日期（PK），月频取月初、日频取交易日 |
| value | DECIMAL(12,4) NULL | 指标值 |
| source | VARCHAR(16) | `tushare` |
| updated_at | TIMESTAMP | 同上 |
| PRIMARY KEY (indicator, ref_date) | | |

> 用单表存所有宏观指标（generic indicator 表），避免每加一个宏观指标就建一张表。indicator 用枚举值约束。

#### 1.4 `raw_margin_balance`（融资融券余额，Tushare 日频）

| 字段 | 类型 | 说明 |
|------|------|------|
| trade_date | DATE | 交易日（PK） |
| rzye | DECIMAL(16,2) NULL | 融资余额（元） |
| rqye | DECIMAL(16,2) NULL | 融券余额（元） |
| source | VARCHAR(16) | `tushare` |
| updated_at | TIMESTAMP | 同上 |
| PRIMARY KEY (trade_date) | | |

> 取交易所级汇总（`margin` 接口），不做标的级明细（`margin_detail`）。

### 2. SQL Migration

- **`mysql/init/15_signal_board.sql`**：fresh 安装建 4 表。
- **`mysql/migrations/016_signal_board.sql`**：已部署库升级用，同 4 表。

> 编号接现有最大：init/14（etf_share）、migrations/015（etf_share）。

### 3. ORM 模型

新建 `backend/app/models/signal_board.py`：
- `RawBondYieldDaily` / `RawIndexDaily` / `RawMacroIndicator` / `RawMarginBalance`
- 克隆现有模型的 `Mapped`/`mapped_column` + `server_default=text(...)` 风格

### 4. 数据拉取

#### 4.1 新建 `backend/app/services/fetcher/signal_fetcher.py`（AkShare 部分，吸收 027）

- `BondBar` / `IndexBar` dataclass
- `fetch_bond_yield(start, end)`：主源 `bond_zh_us_rate`（一次全量按区间过滤，去 NaN），回退 `bond_china_yield`
- `fetch_index_close(index_code, start, end)`：价格指数 `stock_zh_index_daily`（sh/sz 前缀判定：3 开头→sz，其余→sh）
- `fetch_total_return_close(index_code, start, end)`：全收益指数 `stock_zh_index_hist_csindex`（H 代码，**显式传 start/end_date**，否则默认停在 2024-06）
- 复用 `valuation_fetcher._to_dec` 宽松转换

#### 4.2 新建 `backend/app/services/fetcher/macro_fetcher.py`（Tushare 部分）

- `MacroBar` dataclass：`indicator, ref_date, value, source`
- `fetch_macro(indicator, start, end)`：按 indicator 分发到 Tushare 接口：
  - `sf_yoy` → `pro.sf_month` 取 `stk_endval` 算同比
  - `m1_yoy`/`m2_yoy` → `pro.cn_m`
  - `ppi_yoy` → `pro.cn_ppi`
  - `pmi` → `pro.cn_pmi`
- `fetch_margin(start, end)`：`pro.margin` 取 `rzye`/`rqye`（交易所级，按 trade_date 去重留最新）
- `fetch_fund_issue(month_start, month_end)`：`pro.fund_basic` 按 `found_date` 聚合发行规模
- 复用 013 的 `_throttle`/`_split_ranges`/`_resolve_token`（从 `tushare_fetcher` 提取为公共工具或直接 import）
- 异常统一抛 `FetchError`；积分不足（命中 `_PERMISSION_KEYWORDS`）透传 Tushare 原始 msg

> **注意现有架构不对称点**：017/028 的 Tushare 调用不走 `resolve_source` 开关，只校验 token 存在。本任务的宏观/融资融券同样依赖 token，沿用这个模式（不强求开关全开）。但要在 token 缺失时给友好提示。

### 5. 数据保障（ensure，复用 002/024 范式）

新建 `backend/app/services/signal_board_data.py`：

- `ensure_bond_yield(db, start, end)`：MIN/MAX/COUNT 判缺口 → 仅补缺失 → `upsert_bond_yield`
- `ensure_index_close(db, index_code, start, end)`：同构（价格 + 全收益两类）
- `ensure_macro(db, indicator, start, end)`：同构
- `ensure_margin(db, start, end)`：同构
- **PE/PB 复用 024 的 `ensure_valuation`**（不重写）

`storage.py` 新增（克隆现有 UPSERT 范式）：
- `upsert_bond_yield` / `upsert_index_close` / `upsert_macro` / `upsert_margin`

### 6. 计算逻辑

#### 6.1 `backend/app/services/compute/equity_bond_metrics.py`（吸收 027）

```python
def rolling_channel(series, dates, window_years=5) -> dict:
    """滚动均值 + ±1/±2/±3σ 通道。逐日窗口统计（日期差截取子序列），
    返回 mean/p1/p2/p3/n1/n2/n3 七条等长序列。前段不足窗口为 None。
    窗口按 timedelta(days=window_years*365.25) 截取，非固定交易日数。"""

def channel_position(current_ratio, current_mean, p1, p2, n1, n2) -> str:
    """6 档判断（比价越高=股票越便宜）：
    极度昂贵(<-2σ) / 昂贵([-2σ,-1σ)) / 偏贵([-1σ,均值))
    / 中性([均值,+1σ)) / 偏便宜([+1σ,+2σ)) / 便宜(≥+2σ)"""
```

> 与 024 的 `pe_channel`（全周期 min/median/max 静态 5 线）不同，本函数逐日滚动，每个交易日输出一组随时间漂移的通道值。

#### 6.2 `backend/app/services/compute/signal_light.py`（核心新逻辑：信号灯）

```python
Light = Literal["green", "yellow", "red", "grey"]

def light_pe_percentile(pct: float | None) -> Light:
    """PE/PB 分位：<30% 🟢 / 30-70% 🟡 / >70% 🔴。None → grey。"""

def light_equity_bond(ratio: float | None) -> Light:
    """股债比价：>2 🟢 / 1.5-2 🟡 / <1.5 🔴。"""

def light_ma120_deviation(dev: float | None) -> Light:
    """MA120 偏离度（价格/MA120）：<0.985 🟢 / 0.985-1.05 🟡 / >1.05 🔴。"""

def light_drawdown(dd: float | None) -> Light:
    """回撤（%）：>15 🟢 / 5-15 🟡 / <5 🟡。"""

def light_macro(indicator: str, value: float | None, history: list[float] | None = None) -> Light:
    """宏观指标（各口径不同）：
    pmi: >50🟢 / <50🔴
    m1m2_gap: 差值收窄🟢 / 扩大🔴
    sf_yoy: 放量🟢 / 收缩🔴
    ppi_yoy: 上行🟢 / 下行🔴
    margin_rzye: 取历史分位，极低🟢 / 极高🔴"""

def light_mean_anchor(deviation: float | None) -> Light:
    """全收益 vs 5年均线 偏离度：<-10% 🟢 / -10%~+20% 🟡 / >+20% 🔴。"""

def light_fund_issue(scale_percentile: float | None) -> Light:
    """基金发行规模分位：<20%🟢（冰点=底部信号）/ >80%🔴（过热=顶部信号）。"""

def layer_summary(lights: list[Light]) -> Light:
    """单层汇总灯（多数表决）：绿过半→green / 红过半→red / 否则→yellow。grey 不参与表决。"""

def resonance(layer1: Light, layer2: Light, layer3: Light) -> tuple[str, str]:
    """三层共振判断 → (整体状态, 行动建议)。
    全绿→(🟢🟢🟢 历史底部区域, 重点关注，分批建仓区)
    全红→(🔴🔴🔴 历史顶部区域, 警惕，考虑减仓)
    其余→(🟡 不确定, 保持纪律，不做大动作)"""
```

> **阈值来源**：全部忠实设计文档 `docs/refer/估值与信号看板设计.md`。本期硬编码，「阈值可配」列开放问题。

### 7. 编排（主函数）

`signal_board_data.py` 新增：

```python
def build_target_signals(db, symbol, lookback) -> dict:
    """第一层：单标的多维信号。ensure 各数据 → 算各指标 → signal_light 着色 → 组装。
    1. resolve symbol → index_code（复用 024 registry；ETF→指数映射硬编码）
    2. ensure_valuation（PE/PB）+ ensure_bond_yield + ensure_index_close
    3. PE/PB 分位（percentile_rank）+ MA120 偏离（compute_ma）+ 回撤 + 股债比价
    4. 各指标 signal_light → lights
    5. layer_summary(lights) → 第一层汇总灯"""

def build_market_signals(db, lookback) -> dict:
    """第二层：大类资产估值。
    股债比价（沪深300，rolling_channel）+ 全收益 vs 5年均线（H00300/H00985）
    + 创业板/上证比值 + 基金发行热度（Tushare fund_basic 聚合）
    signal_light → lights → layer_summary → 第二层汇总灯"""

def build_capital_macro_signals(db, lookback) -> dict:
    """第三层：资金 + 宏观（全 Tushare）。
    ensure_macro（各指标）+ ensure_margin + ETF 净流入 + 北向
    signal_light → lights → layer_summary → 第三层汇总灯
    token 缺失时：返回结构 + warning「未配置 Tushare Token，第三层不可用」+ 全 grey"""

def build_resonance(layer1, layer2, layer3) -> dict:
    """共振矩阵汇总：三层状态 + 整体判断 + 行动建议。"""
```

### 8. Schema

新建 `backend/app/schemas/signal_board.py`：
- `Light = Literal["green", "yellow", "red", "grey"]`
- `SignalItem`：`key, label, value, display, light, hint`
- `LayerSummary`：`light, items: list[SignalItem]`
- `TargetSignalsData`：`symbol, name_cn, resolved_index, as_of, metrics: list[SignalItem], layer_light, channel_chart(PE通道), equity_bond_chart, warning`
- `MarketSignalsData`：`as_of, metrics: list[SignalItem], layer_light, mean_anchor_chart, equity_bond_chart, ratio_chart`
- `CapitalMacroSignalsData`：`as_of, metrics: list[SignalItem], layer_light, warning`
- `ResonanceData`：`layer1, layer2, layer3, overall_status, action_advice`

### 9. API 路由

新建 `backend/app/api/signal_board.py`，路由前缀 `/api/signal-board`：

| 接口 | 方法 | 参数 | 说明 |
|------|------|------|------|
| `/api/signal-board/target` | GET | `symbol`, `lookback` | 第一层：单标的信号 + PE 通道 + 股债比价 |
| `/api/signal-board/market` | GET | `lookback` | 第二层：大类资产（全收益均线 + 股债比价 + 比值 + 发行热度） |
| `/api/signal-board/macro` | GET | — | 第三层：资金/宏观（Tushare） |
| `/api/signal-board/resonance` | GET | `symbol`, `lookback` | 三层共振汇总（调上述三个 + resonance 合成） |

**业务规则：**
- 不产生 task_id、不写持久化 summary（数据看板）——每次请求即查即算即返回，仅原始数据表缓存。
- `symbol` 支持 ETF 代码（解析到指数）和指数代码直传。ETF→指数映射复用 016 设计的 `resolve_index`（本期硬编码核心映射：512890→930955 等）。⚠️ **注意**：映射目标指数必须在 `index_registry` 中注册（supported=1）才会走估值计算；初版 032 漏配 930955/000922/000015，已由 migration/017 补注册。
- Tushare 未配置时：`/macro` 返回结构化降级（全 grey + warning），不报错；`/target` `/market` 不受影响（走 AkShare）。
- **保留 024 的 `/api/valuation/single` `/overlay` `/indices`**（前端图表组件内部调用）。
- **下线 016 旧端点** `GET /api/valuation`（空路径）+ `services/valuation.py` 的 `get_valuation()` + `_to_legacy`。
- 返回统一 `ApiResponse`。

### 10. 路由注册 + 自愈建表

- `main.py`：`app.include_router(signal_board.router, prefix="/api/signal-board", tags=["signal-board"])`
- 自愈建表 `_ensure_signal_board_tables`（4 张新表），参照 024 `_ensure_valuation_tables`。
- 删除 016 的 `get_valuation` 相关 import 和注册。

### 验收标准（后端）

- [ ] 4 张新表建成功（fresh init/15，已部署 migrations/016）
- [ ] `fetch_bond_yield` / `fetch_index_close` / `fetch_total_return_close` 实测可用
- [ ] `fetch_macro` 各指标（sf/m1m2/ppi/pmi）Tushare 拉取成功（5000 积分）
- [ ] `fetch_margin` 融资融券余额入库
- [ ] `fetch_fund_issue` 基金发行规模按月聚合
- [ ] ensure 函数：已覆盖区间不发请求；仅补缺口；UPSERT 幂等
- [ ] `rolling_channel`：逐日 7 条等长序列，前段不足窗口为 None
- [ ] `signal_light` 各函数阈值正确（忠实设计文档）
- [ ] `layer_summary` 多数表决正确
- [ ] `resonance` 矩阵：全绿→底部 / 全红→顶部 / 其余→不确定
- [ ] GET `/target` 返回单标的多维信号 + 汇总灯
- [ ] GET `/market` 返回大类资产信号 + 全收益均线 + 股债比价
- [ ] GET `/macro` 返回资金/宏观信号（token 缺失时降级 warning）
- [ ] GET `/resonance` 返回三层共振汇总
- [ ] 016 旧端点 `GET /api/valuation` 已移除，`services/valuation.py` 已删
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. 布局（单页长滚动，重构 `ValuationView.vue`）

```
┌─────────────────────────────────────────────────────────┐
│  估值与信号看板                                           │
│  [标的 沪深300▼] [窗口 5年▼] [查询]    数据截至 2026-08-04 │
├─────────────── 三层共振汇总（顶部固定区）─────────────────┤
│  第一层 技术估值：🟢    第二层 大类资产：🟡   第三层 资金宏观：🟢 │
│  整体状态：🟡 偏多但需确认    建议：继续定投，暂不加仓       │
├─────────────── 第一层：技术 + 估值 ──────────────────────┤
│  ┌ MA120偏离  回撤   PE分位  PB分位  股息率  股债比价 ┐    │
│  │ 0.96 🟢   12% 🟡  28% 🟢  35% 🟡  2.6%ⓘ  2.1 🟢 │    │  ← SignalCard 网格
│  └──────────────────────────────────────────────────┘    │
│  ┌ PE 历史通道（复用 ValuationChannelChart）──────────┐   │
│  ┌ 股债比价通道（EquityBondChart）────────────────────┐   │
├─────────────── 第二层：大类资产估值 ────────────────────┤
│  ┌ 股债比价  300全收益偏离  全指偏离  创业板/上证 发行热度┐ │
│  │ 2.1 🟢    -3% 🟢        +8% 🟡   1.2 🔴     冰点 🟢 │  │  ← SignalCard 网格
│  └──────────────────────────────────────────────────┘   │
│  ┌ 沪深300全收益 vs 5年均线（MeanAnchorChart）──────┐    │
│  ┌ 股债比价通道（市场版，完整展示）──────────────────┐    │
├─────────────── 第三层：资金 + 宏观 ─────────────────────┤
│  ┌ 社融  M1M2差  PMI  PPI  融资余额  ETF流入  北向 ┐    │
│  │ 🟢   🟡     🟢  🟢   🟢      🟢      🟡    │    │  ← SignalCard 网格
│  └──────────────────────────────────────────────┘        │
│  ⚠ 未配置 Tushare Token 时：此区显示配置提示，全 grey     │
├─────────────── 数据缺口提示（底部固定区）─────────────────┤
│  ⚠ 本看板部分指标受数据源限制，当前为降级展示：            │
│   • 股息率：仅当日快照，无法算历史分位（缺历史序列源）      │
│   • 红利指数 PB：无数据源，灰显                            │
│   • 万得基金指数（股基/债基相对强弱）：Wind 私有，未展示    │
│   • 北向资金：2024-08 后改为总额披露，精度下降             │
│   完整替代方案见任务文档「开放问题 → 替代数据源调研」       │
└─────────────────────────────────────────────────────────┘
```

### 2. 新组件

#### 2.1 `frontend/src/components/SignalCard.vue`
单指标信号卡片：
- Props：`{ label, value, display, light, hint }`
- light → 背景色/边框色（green/yellow/red/grey），左侧竖条信号灯
- value 主数值 + display 单位 + hint 脚注（如「快照」「5年分位」）

#### 2.2 `frontend/src/components/ResonanceSummary.vue`
顶部三层共振汇总：
- Props：`{ layer1, layer2, layer3, overall, advice }`
- 三层各一个汇总灯（大号）+ 整体状态文字 + 行动建议

#### 2.3 `frontend/src/components/MeanAnchorChart.vue`
全收益指数 vs 5 年均线图（克隆 ValuationChannelChart 双轴范式）：
- 左轴：全收益点位 + MA5y（复用 compute_ma，period 换成 5 年交易日数≈1250）
- 右轴：偏离度%（点位/MA5y - 1）
- markLine：0% 中轴 + ±10%/±20% 参考线

#### 2.4 `frontend/src/components/EquityBondChart.vue`（吸收 027）
股债比价通道图（克隆 ValuationChannelChart）：
- 左轴：比价（红）+ 滚动均值（灰）+ ±1/±2/±3σ（6 条 markLine，颜色由近到远渐淡）
- 右轴：指数点位（浅棕，splitLine 关）
- markPoint 当前点
- 配色：比价越高（股票便宜）用绿色系提示

#### 2.5 复用现有组件
- `ValuationChannelChart.vue`（PE 通道，024 已有，第一层直接用）
- `MetricCard.vue`（备用）

### 3. 页面改版（重写 `ValuationView.vue`）

**控件栏**（复用 `.form-card` + `.form-row` + `button.primary`）：
- 标的下拉：从 `/api/signal-board/indices`（或复用 `/api/valuation/indices`）加载，默认沪深300
- 时间窗口：1/3/5/10 年，默认 5 年（影响分位与均线计算区间）
- 查询按钮

**数据加载**：
- `onMounted` → 并发调 `/resonance`（含三层汇总）+ `/target`（第一层明细）+ `/market`（第二层明细）+ `/macro`（第三层明细）
- 各请求独立 try/catch，单个失败不阻断整页

**三层区块**：纵向排列，每层一个 `.block`（复用 Home.vue 卡片样式：`var(--surface)` + 圆角 + 边框），含 SignalCard 网格 + 对应图表。

**降级提示**：
- 股息率：SignalCard 显示值 + 「快照」hint + grey 灯（不赋绿/黄/红）
- 红利指数 PB：显示「无数据」+ grey
- 第三层无 Tushare：整块替换为「配置 Tushare Token 后可查看资金/宏观信号」+ 指向右上角钥匙图标

### 4. API 封装

`frontend/src/api/index.ts` 新增：
- 类型：`Light`、`SignalItem`、`LayerSummary`、`TargetSignalsData`、`MarketSignalsData`、`CapitalMacroSignalsData`、`ResonanceData`
- `getTargetSignals(params)` / `getMarketSignals(params)` / `getCapitalMacroSignals()` / `getResonance(params)`

### 5. 路由 + 导航

- 路由保持 `/valuation`（重构不新增路由）
- 导航文字 `App.vue:30`「估值」→「估值信号」（或保留，按偏好）

### 验收标准（前端）

- [ ] 单页长滚动布局，顶部共振汇总 + 三层区块
- [ ] ResonanceSummary：三层汇总灯 + 整体状态 + 行动建议
- [ ] SignalCard：每个指标值 + 🟢🟡🔴 灯 + hint，配色正确
- [ ] 第一层：6 个 SignalCard（MA120/回撤/PE/PB/股息率/股债比价）+ PE 通道图 + 股债比价图
- [ ] 第二层：SignalCard 网格 + 全收益 vs 5年均线图 + 股债比价通道图
- [ ] 第三层：SignalCard 网格（社融/M1M2/PMI/PPI/融资/ETF/北向）
- [ ] 股息率降级：显示值 + 「快照」+ grey 灯
- [ ] 红利指数 PB 降级：显示「无数据」+ grey
- [ ] 无 Tushare 时第三层显示配置提示
- [ ] 切换标的/窗口重算
- [ ] 明暗主题切换正确（含信号灯配色）
- [ ] `npm run build`（vue-tsc）通过

---

## 与历史 task 的关系

| Task | 关系 | 处理 |
|------|------|------|
| 016 估值温度计 | **下线** | 删除 `services/valuation.py` + `/api/valuation` 空端点 + `_to_legacy`；016 的 py_mini_racer 自愈酌情保留（lg 源仍依赖） |
| 024 估值看板 v2 | **复用 + 保留** | 数据通路（表/fetcher/ensure/compute）全部保留；前端页面被重写吸收；`/api/valuation/single` `/overlay` `/indices` 保留供内部调用 |
| 027 股债比价 | **吸收** | 027 不再独立实现。其设计内容（国债表/指数点位表/rolling_channel/股债比价图）并入 032。TASKS.md 027 标注「并入 032」 |

---

## 数据复用与隔离策略

| 数据 | 表 | 来源 | 复用原则 |
|------|----|----|----------|
| 指数 PE/PB | `raw_index_valuation_daily`（024） | lg + csindex | **复用 024** `ensure_valuation` |
| 指数注册 | `index_registry`（024） | 预置 | **复用 024** |
| 十年期国债 | `raw_bond_yield_daily`（新建） | AkShare bond_zh_us_rate | ensure + UPSERT |
| 指数点位（价格+全收益） | `raw_index_daily`（新建） | AkShare | ensure + UPSERT |
| 宏观指标 | `raw_macro_indicator`（新建） | Tushare | ensure + UPSERT，generic 表 |
| 融资融券 | `raw_margin_balance`（新建） | Tushare | ensure + UPSERT |
| ETF 份额/北向 | 不落库（017 模式） | Tushare（已用） | 实时拉取 |
| 基金发行 | 按需聚合（不落库或轻落库） | Tushare fund_basic | 月度聚合 |

> Tushare 宏观/融资融券数据**落库**（频率低、要算历史趋势，避免每次请求都打 Tushare 积分）；ETF 份额/北向/基金发行沿用 017 的**不落库实时拉取**模式。token 缺失时降级，不影响第一二层。

---

## 开放问题（后续迭代）

### 替代数据源调研（针对当前降级的 3 个硬伤）

> 本看板有 3 个指标因 AkShare + Tushare 均无法覆盖而降级展示。以下为替代获取渠道的调研结论，供后续迭代决策。

#### 缺口一：指数股息率历史序列（决定股息率分位能否计算）

| 渠道 | 可行性 | 代价 | 说明 |
|------|--------|------|------|
| **理杏仁** | ✅ 有完整历史走势 + 分位点 | 💰 付费会员 + 🚧 无官方 API | 页面可导 CSV，程序化需爬虫（合规风险）或联系企业授权 |
| **蛋卷基金** | ⚠️ 仅当前分位点 | 免费 | 给「比过去 N% 时间低」的分位，但**无历史日序列**，算不了分位曲线 |
| **中证官网 FactSheet PDF** | ⚠️ 仅当日快照 | 免费 | 每日 PDF 含当日股息率，无历史；但可**每日定时抓取累积** |
| **东方财富/Choice** | ⚠️ 个股级 | 免费/付费 | 有个股股息率，可按成分股加权自算，但权重数据本身也难拿 |
| **自建快照累积** | ✅ 长期可行 | 免费 | 每日定时落库 csindex 当日快照，半年/一年后拼出可用历史 |

**务实结论**：短期接受「只显示当前值」；中期走「每日快照累积」；若愿付费，理杏仁是唯一能立即拿到完整历史的渠道。

#### 缺口二：红利类指数 PB（中证红利/红利低波等）

| 渠道 | 可行性 | 代价 | 说明 |
|------|--------|------|------|
| **理杏仁** | ✅ 有 | 💰 付费会员，无官方 API | 同上 |
| **成分股加权自算** | ⚠️ 重活 | 免费但费时 | 取成分股（Tushare `index_weight`，5000 积分）+ 个股 PB（Tushare `daily_basic`），按权重加权 |
| **中证 FactSheet** | ❌ PDF 无 PB 列 | — | — |

**务实结论**：要么付费理杏仁，要么走成分股加权自算（Tushare 5000 积分够用，工作量中等）。

#### 缺口三：万得基金指数（混合债一级/偏债混合，用于股基/债基相对强弱）

| 渠道 | 可行性 | 代价 | 说明 |
|------|--------|------|------|
| **Wind 终端** | ✅ 唯一权威 | 💰💰 高额订阅 | .WI 私有指数，不在公开渠道发布 |
| **中证/中债指数** | ⚠️ 口径不同 | 免费 | 有底层债券指数，但**无对应的公募基金分类业绩指数** |
| **自建合成** | ⚠️ 近似 | 免费 | 按 Wind 口径筛成分基金（天天基金）→ 取净值 → 加权合成，与官方有偏差 |
| **中证偏股基金指数** | ✅ 近似替代 | 免费（Tushare `index_daily`） | 覆盖股基侧；债基侧无公开等价物，只能做半套 |

**务实结论**：Wind 私有指数无法合规获取；建议降级用「中证偏股基金指数」做股基侧近似，债基侧暂缺。

#### 💡 关键洞察：「每日快照累积」可同时解决缺口一+二

每日定时跑一次，把 csindex/lg 当日所有指数的估值快照（PE/PB/股息率）全部落库，时间一长就是完整历史序列。这一个基础设施能**同时补齐股息率历史和红利指数 PB** 两个缺口，且对 021（股息率回测）也有用。建议作为独立 task 立项（估值快照定时落库），不阻塞 032 交付。

---

### 后续迭代项

- [ ] **估值快照定时落库**（独立 task）：每日定时抓取 csindex + lg 全指数估值快照入库，长期累积拼出股息率/PB 历史序列。同时解决缺口一、二，并解锁 021 股息率回测。
- [ ] **第三方估值源接入**（理杏仁）：若愿付费，联系理杏仁企业授权获取 API，立即补齐股息率历史 + 红利指数 PB。
- [ ] **信号阈值可配置化**：本期硬编码设计文档阈值；后续做前端设置入口。
- [ ] **三层共振回测验证**：用历史数据回测「全绿买入、全红卖出」的实际收益，验证信号体系有效性。
- [ ] **锚点触发预警**（设计文档 7.1）：三层全绿+回撤>15% 等复合触发条件，推送提醒。
- [ ] **持仓联动**（设计文档 7.3）：接持仓数据，给持仓健康度评分。
- [ ] **股基/债基相对强弱补全**：自建合成 Wind 基金指数，或采购 Wind 终端。
- [ ] **北向资金口径**：2024-08 后交易所改为总额披露，AkShare/Tushare 同受影响，无法靠换源解决。
