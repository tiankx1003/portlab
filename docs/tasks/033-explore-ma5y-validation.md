# 033 — 探索页：MA5Y notebook 对齐验证（股债比价 + 五年之锚 + 锚定定投回测）

## 目标

**一句话**：现有 `/valuation` 估值页**一行不动**，新增「探索」沙盒页（`/explore`），把 `~/git_repo/jupylab/MA5Y.ipynb`（仓库外工作本，下称 notebook）的三个核心能力做出来并与 notebook 对数验证；验证通过后再分批合并回正式页面。

### 为什么需要探索页

现行估值页的股债比价图（`EquityBondChart`）架子与 notebook 一致（4 子图），但内核存在**正确性级差距**（见下节），直接改正式页风险高；notebook 里的「五年之锚定投回测」则是全新功能。用独立沙盒页承载：后端走独立的 explore 模块、前端独立路由，与正式代码零耦合，验证放心后再迁移。

---

## 背景：notebook 是什么、现行差在哪

### notebook 的三个核心（需求规格 = 这三段代码）

| 功能 | notebook 位置 | 内容 |
|------|-------------|------|
| 股债比价 | cell 11 `fetch_real_data` + `plot_interactive_ratio` | 数据 **2005 年全历史**：Tushare 全收益指数日线（H00300.CSI）+ PE-TTM（`index_dailybasic`，不支持时 fallback `ak.stock_index_pe_lg`）+ 10Y 国债（`ak.bond_zh_us_rate`）。outer join 后 `dropna(close, pe, bond_yield)` 精确对齐。`ratio = (1/PE×100) / bond_yield`。**1260 个交易日（252×5）rolling 均值/σ**（`min_periods=1`、pandas 样本 std 即 ddof=1）；**percentile = 全历史 `rank(pct=True)`**。4 子图（比例 35/22/22/21）：①ratio+均值+**±1σ 浅带+±1.5σ 深带**+指数右轴 ②股债收益率对比 ③分位数（80/20 参考线）④PE+**全历史均值横线**+指数右轴 |
| 五年之锚可视化 | cell 4 | 收盘价 + **1260 日均线** + ±15% 通道（upper/lower）+ **+28% 卖出线** + 60 日均线（sell_test 找卖点）+ 通道填充 |
| 锚定定投回测 | cell 6 `backtest_drip` | 见 P2 详细参数 |

### 现行实现逐项差距

**股债比价（`backend/app/services/signal_board_data.py:470` `_build_equity_bond_for_target` + `compute/equity_bond_metrics.py`）**

| 维度 | notebook | 现行 portlab | 级别 |
|------|----------|-------------|------|
| 数据范围 | 2005 全历史 | 只拉 lookback 窗口（`_LOOKBACK_DAYS` 1y/3y/5y/10y） | **正确性**：lookback=5y 时通道第一天的"过去5年"= 窗口内全部数据，**通道形状随 lookback 切换而变、前段系统性失真** |
| 滚动窗口 | 固定 1260 交易日 | 日历年 1825 天截取 | 口径差 |
| σ 口径 | 样本 std（ddof=1），逐点有值（min_periods=1） | 总体 std（pstdev），窗口内 <2 样本断档 | 小 |
| 通道档位 | ±1σ + ±1.5σ 两档 | 仅 ±1σ | 视觉 |
| 分位数 | 全历史 rank | 窗口内 rank | **参照系** |
| PE 均值线（子图4） | 有 | 无 | 小 |

**五年之锚（`signal_board_data.py:633` `_build_mean_anchor` + `frontend/src/components/MeanAnchorChart.vue`）**：第二层已有八成内核——MA5y + ±15% + **+28% 卖出线** + ma60 + 偏离信号灯 `light_mean_anchor`，且**预热处理正确**（前推两个窗口拉数据再切片展示，`signal_board_data.py:640` 附近——这正是股债比价该抄的模式）。缺：

1. 只固定第二层 H00300，第一层选任何标的看不到自己的锚图；
2. 均线窗口 1250 日（250×5）vs notebook 1260 日（252×5），统一为 1260；
3. **`backtest_drip` 回测完全没有**。

---

## 用户已确认的设计决定

| 维度 | 决定 |
|------|------|
| 正式页 | `/valuation` **保持不变**，探索期不碰 `signal_board_data.py` 现有函数 |
| 新页面 | 新增「探索」页（`/explore`），导航入口，定位是验证沙盒 |
| 后端组织 | 新建 `services/explore_data.py` + `api/explore.py`（路由前缀 `/api/explore`），复用现有 fetcher/storage 落库通路，不复制取数代码 |
| 回测落库 | 探索期 backtest_drip **实时计算不落库**（参照 `run_drawboard_realtime` 模式），验证通过接入正式框架时再落库 + MCP 暴露 |
| 验证方式 | 与 notebook **对数**（同参数同日期数值对比），通过后才谈合并 |
| 合并路径 | 验证后分批合并回正式页（见文末），不在本任务范围 |

---

## 实施计划

### P0 — 股债比价：全历史口径通道（价值最大）

**后端**（`explore_data.py`）：

1. `build_explore_equity_bond(symbol, lookback)`：
   - 数据拉取**全历史**：`ensure_valuation` 从 registry 源最早可得日起（lg 宽基 2005 起；csindex 红利 2018 起）拉到今天，`ensure_bond_yield` 同理（`bond_zh_us_rate` 本就一次全历史 1990 起），幂等增量落库；
   - 对齐逻辑对齐 notebook：以 PE 日期为主干，国债当日精确匹配，缺失整行 None（不 ffill，与 notebook `dropna` 等价）；
   - 滚动计算改为「**全历史算 + 展示切片**」：rolling 与 percentile 在全历史上算，输出只截 lookback 区间（抄 `_build_mean_anchor` 的前推思路）。
2. `compute/equity_bond_metrics.py` **不动**（正式页在用），在 explore 模块内新建 `rolling_channel_v2`：
   - `window_mode`: `"trading_days"`（默认，窗口=1260 交易日）| `"calendar_years"`（兼容旧口径，用于对照视图）；
   - 样本 std（ddof=1）、`min_periods=2`；
   - 输出 `mean` + `p1/n1`（±1σ）+ `p15/n15`（±1.5σ）。
3. `GET /api/explore/equity-bond?symbol=&lookback=` 返回 chart：`ratio/mean/p1/n1/p15/n15/stock_yield/bond_yield/percentile(全历史)/pe_ttm/pe_mean(常数)/index_close`。

**前端**：新组件 `EquityBondChartV2.vue`（可复制 `EquityBondChart.vue` 改）：两档通道带（±1σ 浅 + ±1.5σ 深）、子图4 加 PE 均值 markLine、子图比例 35/22/22/21。

**对照验证（页面核心玩法）**：同屏提供口径切换（全历史 1260 交易日 / 现行窗口日历年），直观看出通道差异——这既是验证工具，也是给"是否合并"提供证据。

### P1 — 五年之锚进单标的

1. `build_explore_anchor(symbol)`：泛化 `_build_mean_anchor`——`_ETF_INDEX_MAP` 扩展全收益 H 代码映射（510300→H00300 等，csindex 源实测可用：H00300/H00985/H00922，**必须显式传 start/end 否则停在 2024-06**）；无全收益源时降级用价格指数并在标题标注口径；
2. 均线统一 **1260 日**；保留 ma60 / ±15% / +28% 卖出线；
3. `GET /api/explore/anchor?symbol=`；前端复用 `MeanAnchorChart.vue`（series 结构不变，ma_period 由后端改）。

### P2 — MA5Y 锚定定投回测（notebook 的灵魂功能）

**策略规则（忠实 notebook cell 6）**：

| 规则 | 内容 |
|------|------|
| 定投日 | 每周一（`weekday==0`），按当日收盘价判定区间 |
| `< lower`（MA−15%） | 重仓买入 **1600** |
| `[lower, MA5Y)` | 加仓买入 **400** |
| `[MA5Y, upper)`（MA+15%） | 常规定投 **100** |
| `[upper, sell_line)`（MA+28%） | 观望，投 0 |
| 突破卖出线 | `pre_close < sell_line < close` 从下向上突破 → **卖出 50% 持仓** |
| 现金收益 | 每周先计息 `WEEKLY_RATE = 0.0006`（万六） |
| 手续费 | 双边费率 `transaction_cost`，默认 0，可设 0.001（千一） |
| 起点 | notebook 从 2010-01-01 起，做成可配参数 |

**实现**：`compute/ma5y_backtest.py` 纯函数引擎 + `POST /api/explore/ma5y-backtest`（实时计算不落库）。输出：逐周资产序列（cash/shares/市值/累计投入）、trades 明细、指标（总投入/总资产/收益率/XIRR/最大回撤/买卖次数/每次卖出记录）。

**前端**：探索页第三块——参数表单（分档金额/通道比例/周息/手续费/起点）+ 图表（价格+通道+买卖点标注在上，资产净值 vs 累计投入在下）+ 指标卡 + trades 表。

### P3 — 打磨（可延后）

- hover 展示格式对齐 notebook（x unified 风格）；
- 全历史数据 payload 明显变大，图表输出**必须降采样**（参照 MCP 侧 ~80 点惯例，保留通道拐点）；
- 暗色主题适配（新组件照抄现有 themeColors 模式）。

---

## 探索页信息架构

```
/explore（导航新增「探索」入口）
├── 说明条：本页为验证沙盒，与 notebook 对数通过后将合并回正式页
├── ① 股债比价对照
│   ├── 标的切换（registry 指数）+ lookback + 口径切换（全历史1260日 / 现行窗口）
│   └── EquityBondChartV2（4 子图）
├── ② 五年之锚
│   ├── 标的切换（ETF/指数，全收益优先）
│   └── MeanAnchorChart（close/ma/ma60/±15%/卖出线）
└── ③ MA5Y 定投回测
    ├── 参数表单 + 运行
    └── 回测图表 + 指标 + trades
```

---

## 对数验证与验收标准

### 验证方法

notebook 重跑（或读其输出 cell）取数，与 explore API 同日数值对比。抽 3 个代表性日期（如 2014 年中、2019 年初、最近一个交易日）：

| 指标 | 容差 | 说明 |
|------|------|------|
| ratio / stock_yield / bond_yield | <0.1% | 数据源不同（lg vs Tushare PE）可能有微差 |
| rolling mean / std | <0.5% | 窗口定义细微差（1260 交易日截取边界） |
| percentile | <1 个百分点 | 全历史 rank 参照系须一致 |
| backtest 最终资产/份额/买卖次数 | 完全一致或差异可解释 | 同参数（2010 起、万六、费率 0） |

### 验收标准

1. 探索页三块功能可用，`/valuation` 正式页行为与合并前完全一致（零改动）；
2. 上表对数通过，差异均在容差内或有明确解释（记录在任务文档或 PR 描述）；
3. 口径对照视图能清楚展示新旧通道差异；
4. 新代码不修改 `signal_board_data.py` / `equity_bond_metrics.py` / `EquityBondChart.vue` / `MeanAnchorChart.vue`（后者如需改 ma_period，通过后端输出而非改组件）。

---

## 数据源与风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| PE 历史深度：lg 宽基 2005 起 ✅、csindex 红利仅 2018 起 | 红利类指数全历史通道起点晚 | 接受并标注数据起点；不影响沪深300/500/上证等主力指数 |
| 中证800/1000 无 Tushare PE | notebook 用 lg fallback | portlab registry 多源机制已覆盖，沿用 |
| `bond_zh_us_rate` 全历史 1990 起 ✅ | 无 | 首次全历史落库量约 6千行，一次性 |
| 全历史 PE 落库量（沪深300 约 5千行/指数） | 首次拉取慢 | ensure_* 幂等增量，只慢第一次 |
| notebook 数据源是 Tushare PE（portlab 是 lg/csindex） | ratio 绝对值有微差 | 对数容差放宽到 0.1%，重点验证通道形状与分位 |

---

## 后续合并路径（本任务之后，另行立项或并入后续任务）

1. **股债比价**：`rolling_channel_v2` 与全历史数据通路验证通过后，替换 `_build_equity_bond_for_target` 的窗口内算法（正式页行为升级），`EquityBondChartV2` 替换 `EquityBondChart`；
2. **五年之锚**：`_build_mean_anchor` 泛化逻辑上收到第一层，ma_period 统一 1260；
3. **MA5Y 回测**：接入正式回测框架（落库表 + task_id 幂等 + MCP `run_ma5y_backtest` 工具 + 回测页入口），届时探索页对应块下线。

## 关键代码索引（实现时直接定位）

| 位置 | 作用 |
|------|------|
| `~/git_repo/jupylab/MA5Y.ipynb` cell 11 | 股债比价需求规格（fetch_real_data + plot_interactive_ratio） |
| 同上 cell 4 / cell 6 | 五年之锚可视化 / backtest_drip 回测规格 |
| `backend/app/services/signal_board_data.py:470` | 现行股债比价组装（保持不动） |
| `backend/app/services/signal_board_data.py:633` | 现行五年之锚（预热模式参考 + P1 泛化对象） |
| `backend/app/services/compute/equity_bond_metrics.py` | 现行滚动通道（保持不动，v2 新建） |
| `backend/app/services/storage.py` | `ensure_valuation` / `ensure_bond_yield` / `ensure_index_close` 落库通路 |
| `frontend/src/components/EquityBondChart.vue` / `MeanAnchorChart.vue` | V2 组件的复制起点 |
| `backend/app/api/drawboard.py` 的 realtime 模式 | P2 不落库回测的 API 参考 |
