# 023 — 策略擂台（横向对比看板）

## 目标

新增第八个页面：**策略擂台**。横向对比层——把现有所有策略回测的结果放一起比，回答用户最自然的提问：

- 「**512890 上，定投 vs MA120 vs 回撤买入 vs 网格，过去 3 年谁赢？**」（同标的多策略）
- 「**MA120 策略，红利 vs 红利低波 vs 沪深300，哪个最适合？**」（同策略多标的）

**零新策略、零新计算引擎**——纯消费现有 `result_*_summary` 表，前端做归一化与对比渲染。是「**放大现有四个策略价值**」的杠杆任务，投入产出比最高。

> **与 011 首页「最近记录」的区别**：011 是「最近跑过的回测列表」（时间序），本任务是「**主动选多个对比**」（分析序）。011 回答「我跑过啥」，023 回答「哪个更好」。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [003 — 定投回测](./003-dca-compute-engine.md)（消费 `result_dca_summary`）
- [007 — MA120](./007-ma120-strategy-backtest.md)（消费 `result_ma120_summary`）
- [015/019 — 回撤看板](./019-drawboard-v2.md)（消费 `result_drawboard_summary`，**需 019 完成补表**）
- [020 — 网格交易](./020-grid-trading.md)（消费 `result_grid_summary`，**需 020 完成**）
- [007 — MA120](./007-ma120-strategy-backtest.md)（图表/卡片范式）

> **强依赖**：本任务需四个策略都有持久化的 summary 表才能对比。当前 drawboard（019）和 grid（020）的表未建，故**本任务需在 019、020 之后实施**。

---

## Part A：后端

### 1. 跨策略结果聚合查询（核心）

新建 `backend/app/services/arena.py`：

```python
SUPPORTED_STRATEGIES = {
    'dca': ('result_dca_summary', 'calc_dca_backtest'),
    'ma120': ('result_ma120_summary', 'calc_ma120_backtest'),
    'drawboard': ('result_drawboard_summary', 'calc_drawboard_backtest'),
    'grid': ('result_grid_summary', 'calc_grid_backtest'),
}

def list_strategy_results(
    db, symbol: str | None, strategy: str | None, start: date | None, end: date | None
) -> list[StrategyResultItem]:
    """跨四张 summary 表查询，返回统一结构的对比项。
    每项含：task_id, strategy, symbol, symbol_name, start_date, end_date,
            total_return_rate, annualized_return, max_drawdown, sharpe(若有),
            buy_count, sell_count, params_summary(人类可读的参数摘要)。"""
```

- 用 UNION 或分别查询四表后合并（四表字段近似但不完全一致，需统一映射）。
- `params_summary`：把各策略特有参数拼成一句话（如「MA120: 阈值0.985 步长0.01 batch」「网格: 中枢4.2 间距3% 5×5」）。

### 2. 净值序列归一化（供对比曲线）

```python
def get_normalized_nav(db, task_id: str, strategy: str) -> list[tuple[date, float]]:
    """从对应 calc 表读 market_value（或 nav），归一化到起点=100。
    返回 [(date, nav_100)]，供前端多曲线叠加。"""
```

- 各策略的 calc 表都有 market_value/nav 字段，归一化后可比。
- drawboard 的 calc 表（019 新建）、grid 的 calc 表（020 新建）字段对齐。

### 3. 数据模型

**不新建表**——纯读现有四组 calc/result 表。无 ORM 新增、无 migration。

### 4. Schema（`schemas/arena.py`）

- `ArenaQuery`：mode（cross_strategy / cross_symbol）、symbol（cross_strategy 模式必填）、strategy（cross_symbol 模式必填）、symbols[]（cross_symbol）、start/end（可选过滤）
- `StrategyResultItem`：上述统一字段
- `ArenaData`：`items[]`（对比项列表）+ `nav_series{ task_id: {dates[], nav[]} }`（归一化净值）

### 5. API 路由（`api/arena.py`）

路由前缀 `/api/arena`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/arena/compare` | GET | 参数 mode/symbol/strategy/start/end → 返回 ArenaData（items + nav_series） |

业务规则：
- 跨表查询，缺表（如 grid 未实现）则跳过该策略，不报错。
- 返回每项的 strategy/symbol，前端据此分类着色。
- 无 task_id、无持久化（本任务是即查即返回的对比视图）。

### 6. 路由注册

`main.py`：`app.include_router(arena.router, prefix="/api/arena", tags=["arena"])`。

### 验收标准（后端）

- [ ] 跨四张 summary 表查询正确合并
- [ ] 字段统一映射（各策略特有字段降级为 params_summary）
- [ ] 归一化净值正确（起点=100）
- [ ] cross_strategy（固定 symbol 列所有策略）与 cross_symbol（固定策略列所有 symbol）两种模式
- [ ] 缺策略表时优雅跳过
- [ ] 返回统一 ApiResponse，Swagger 可测

---

## Part B：前端（克隆 MA120 主题 + 对比特色）

### 1. 页面与控件（克隆 Ma120Backtest.vue 表单范式）

新建 `frontend/src/views/ArenaView.vue`：

| 控件 | 说明 |
|------|------|
| 模式切换 | radio：同标的多策略 / 同策略多标的 |
| 标的（cross_strategy） | 搜索输入，单选（如 512890） |
| 策略（cross_symbol） | select：dca/ma120/drawboard/grid，单选 |
| 标的列表（cross_symbol） | 多选搜索（多个 ETF） |
| 起止日期 | 可选过滤 |
| 「对比」按钮 | button.primary |

### 2. 归一化净值对比图（`ArenaNavChart.vue`，克隆 Ma120Chart.vue）

- 多条净值折线叠加（每策略/每标的一条），起点=100。
- 颜色区分（COLOR_UP/DOWN/紫/橙等），legend 可开关。
- 复用 Ma120Chart 的 themeColors/dataZoom/tooltip。
- tooltip：日期 + 各曲线当日净值，带颜色。

```
净值(归一化, 起点=100)
│
│            ╱── MA120 (最优, 绿色高亮)
│         ╱──╱── 定投
│      ╱──╯───── 网格
│   ╱──╯─────── 回撤买入
│──╯
└──────────────────→ 时间
```

### 3. 指标对比表（核心，表格非卡片）

横排每策略/标的一列，指标为行：

| 指标 | 定投 | MA120 | 网格 | 回撤买入 |
|------|------|-------|------|----------|
| 总收益率 | 12.3% | **45.6%** 🟢 | 28.1% | 18.9% |
| 年化 | 3.9% | **12.1%** 🟢 | 7.2% | 5.1% |
| 最大回撤 | -15% | -22% | **-8%** 🟢 | -18% |
| 夏普 | 0.3 | **0.6** 🟢 | 0.5 | 0.4 |
| 买卖次数 | 36/0 | 8/3 | 120/118 | 5/1 |
| 参数 | 每月1000 | 阈值0.985... | 中枢4.2... | 阈值20... |

- **每行最优值绿色高亮**（最大收益/最小回撤/最高夏普）。
- 收益类红色、回撤类绿色（A 股惯例）。

### 4. 散点图（可选辅助）

- 横轴年化波动、纵轴年化收益，每个策略/标的一点。
- 直观看出「风险收益比」谁优（左上角最优）。

### 5. 路由与导航

- `router/index.ts`：`{ path: '/arena', name: 'arena', component: ArenaView }`
- `App.vue` nav-links：`<RouterLink to="/arena">策略擂台</RouterLink>`，排在「组合回测」之后。

### 6. API 封装

`api/index.ts`：`compareArena(params)` + 类型 `StrategyResultItem`/`ArenaData`。

### 验收标准（前端）

- [ ] 导航「策略擂台」入口
- [ ] 两种模式切换（cross_strategy / cross_symbol）
- [ ] 归一化净值多曲线对比，颜色区分，legend 可开关
- [ ] 指标对比表：每行最优值绿色高亮
- [ ] 收益红/回撤绿配色
- [ ] 散点图（风险收益比）正确
- [ ] 缺策略时优雅跳过（不显示空列）
- [ ] 明暗主题适配

---

## 数据复用与隔离

| 数据 | 来源 | 复用 |
|------|------|------|
| 各策略 summary | result_dca/ma120/drawboard/grid_summary | 直接读 |
| 各策略净值 | calc_dca/ma120/drawboard/grid_backtest | 归一化 |
| 图表/主题 | Ma120Chart.vue | 克隆范式 |

> **本任务几乎零新代码**——无新表、无新引擎、无新计算。是四个策略完成后的「放大器」。

---

## 落地节奏

**前置**：必须 019（drawboard 补表）、020（grid 建表）完成后，四个策略才有可比的持久化结果。

实施轻量：
- 后端：一个跨表查询 service + 一个 GET 接口。
- 前端：归一化净值图（克隆 Ma120Chart）+ 对比表（新组件）。

---

## 开放问题

- [ ] **跨策略参数对齐**：各策略参数差异大（定投按月、网格按格），对比时是否标注「参数不可直接类比」。
- [ ] **风险调整收益**：除夏普外，加 Sortino（仅下行波动）、Calmar（收益/最大回撤）。
- [ ] **组合 vs 单标的策略**：022 组合回测完成后，擂台可对比「组合策略 vs 单标的策略」。
- [ ] **保存对比结果**：一期即查即返；后续可保存对比快照供分享。
- [ ] **回测区间一致性校验**：对比项若起止日期不同，结果可比性下降；可加「同区间过滤」。
