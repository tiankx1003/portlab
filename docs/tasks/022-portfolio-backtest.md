# 022 — 组合回测（含有效前沿 / 最优权重）

## 目标

新增第七个策略回测页：**组合回测**。从「单标的」跃迁到「**多标的组合**」——回答红利投资者持有多只相关 ETF 时的核心问题：「**这一篮子整体表现如何、有没有更好的权重配比、能不能降风险**」。
| 模式 | 说明 | 复杂度 |
|------|------|--------|
| **指定权重回测** | 用户手填权重（红利30%+红利低波20%+沪深300 50%），算组合收益/回撤/波动 | 中 |
| **有效前沿 / 最优权重** | 马科维茨 MPT，求「同等风险下收益最高」的最优权重组合 | 高（二次规划） |

> **与 018 的区分**：018 事件看板里的相关性热力图是「**事件窗口短期相关**」；本任务是「**长期结构性组合回测 + 权重优化**」。两者计算同源（协方差矩阵），但 022 是策略回测形态（有 task_id、持久化、净值曲线），018 是事件分析。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（`ensure_price_data`，多标的批量补数）
- [003 — 定投回测](./003-dca-compute-engine.md)（`annualized_return`/`xirr`/`max_drawdown`）
- [007 — MA120](./007-ma120-strategy-backtest.md)（DB/task_id/图表/卡片范式）

> **新增数学依赖**：`scipy.optimize.minimize`（求有效前沿的最优权重）或纯 numpy 二次规划。`backend/pyproject.toml` 加 `scipy` 或 `numpy`（若尚未引入）。

---

## Part A：后端

### 1. 计算引擎

新建 `backend/app/services/compute/portfolio.py`。

#### 1.1 多标的数据加载与对齐

```python
def load_aligned_returns(
    db, symbols: list[str], start: date, end: date, source: str
) -> dict[str, list[float]]:
    """加载多标的日收益率，按日期对齐（取所有标的都有数据的交易日交集）。
    返回 {symbol: [daily_returns...]}，长度一致。"""
```

- 缺数据的标的用 `ensure_price_data` 补拉。
- 日期对齐：取所有标的的交易日**交集**（避免 NaN）。

#### 1.2 组合统计

```python
def portfolio_stats(weights: list[float], mean_returns: np.ndarray, cov_matrix: np.ndarray, rf: float = 0.025) -> dict:
    """给定权重，算组合的年化收益、年化波动率、夏普比率。
    - 年化收益 = weights · mean_returns × 252
    - 年化波动 = sqrt(weights · cov · weights) × sqrt(252)
    - 夏普 = (年化收益 - rf) / 年化波动
    """
```

#### 1.3 有效前沿求解（核心，二次规划）

```python
def efficient_frontier(mean_returns, cov_matrix, rf: float, n_points: int = 50) -> list[dict]:
    """求有效前沿上的 n_points 个最优组合。
    对每个目标收益水平，最小化组合方差（权重和=1，权重≥0 可选允许做空）。
    用 scipy.optimize.minimize(SLSQP)，约束：sum(weights)=1, target_return=目标。"""
```

- 输出每个前沿点的 `{weights[], return, volatility, sharpe}`。
- 约束选项：`allow_short`（允许负权重做空）默认 false。
- **最小方差组合**（前沿最左点）与**最大夏普组合**（切点）单独标出。

#### 1.4 指定权重回测（净值时序）

```python
def backtest_fixed_weights(
    db, symbols, weights, start, end, source, rebalance: str = 'monthly'
) -> list[dict]:
    """按指定权重回测，定期再平衡（monthly/quarterly/none=买入持有不调）。
    逐日算组合净值。返回 [{date, nav, ...}]。"""
```

- 再平衡逻辑：到再平衡日，把组合调回目标权重。
- `none` 模式：初始按权重买入后不再调整，让各标的自然漂移。

#### 1.5 task_id

```
port_{symbols_hash}_{start}_{end}_{mode}_{weights_hash}_{rebalance}_{source}
```

- `symbols_hash` / `weights_hash`：排序后拼接的短哈希，保证确定性。
- `mode`：`fixed`（指定权重）/ `frontier`（有效前沿）。

### 2. 数据模型

#### 2.1 `result_portfolio_summary` 表

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| symbols | VARCHAR(255) | 逗号分隔的标的列表 |
| mode | VARCHAR(8) | fixed / frontier |
| weights | VARCHAR(255) | JSON 权重数组 |
| rebalance | VARCHAR(8) | monthly/quarterly/none |
| start_date / end_date | DATE | |
| annual_return / annual_volatility / sharpe / max_drawdown / total_return | DECIMAL | 组合指标 |
| rf | DECIMAL(8,4) | 无风险利率假设 |
| allow_short | TINYINT(1) | 是否允许做空 |
| KEY idx_symbols (symbols) | | |

#### 2.2 `calc_portfolio_nav` 表（逐日净值）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| trade_date | DATE PK | |
| nav | DECIMAL(12,6) | 归一化净值（起点=1） |
| drawdown | DECIMAL(8,4) | 当日回撤(%) |
| KEY idx_task (task_id) | | |

> 有效前沿模式：每个前沿点生成一个 task_id（或一个 task 含多组 nav）。一期建议**每个前沿点独立 task**，前端汇总展示。

新建 `backend/app/models/portfolio.py`，注册 `models/__init__.py`。

### 3. SQL Migration

- `mysql/init/0X_portfolio.sql`：两张表。
- `mysql/migrations/0XX_portfolio.sql`：已部署库用。

### 4. Schema（`schemas/portfolio.py`）

- `PortfolioRequest`：symbols[]、mode（fixed/frontier）、weights[]（fixed 模式必填）、rebalance、rf、allow_short、start/end
- `PortfolioChartData`：
  - `nav_series[]`：组合净值（fixed 模式）或多个前沿点净值（frontier 模式）
  - `benchmark_nav[]`：等权组合 / 沪深300 归一化净值对照
  - `frontier`（frontier 模式）：`{volatilities[], returns[], sharpes[], weights_matrix[][]}` + 单标的点位 + 最小方差/最大夏普标记
  - `correlation_matrix`：标的两两相关系数（供热力图）
- `PortfolioSummary`：与 summary 表对应

### 5. API 路由（`api/portfolio.py`）

路由前缀 `/api/backtest/portfolio`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/backtest/portfolio` | POST | 提交参数 → ensure 多标的数据 → 计算（fixed 或 frontier）→ 落库 → task_id |
| `/api/backtest/portfolio/{task_id}/chart` | GET | 返回 PortfolioChartData |
| `/api/backtest/portfolio/{task_id}/summary` | GET | 返回 PortfolioSummary |

业务规则：
- 多标的批量 `ensure_price_data`。
- fixed 模式：校验 weights 与 symbols 等长、和≈1（±0.01 容差）。
- frontier 模式：忽略 weights，求前沿。
- 命中缓存返回。

### 6. 路由注册

`main.py`：`app.include_router(portfolio.router, prefix="/api/backtest", tags=["backtest"])`。

### 验收标准（后端）

- [ ] 多标的日收益率正确加载与日期对齐
- [ ] 协方差矩阵对称、对角线为各标的方差
- [ ] portfolio_stats（收益/波动/夏普）计算正确
- [ ] 有效前沿求解收敛，前沿点单调（收益↑时波动↑）
- [ ] 最小方差组合与最大夏普组合正确标出
- [ ] 指定权重回测：再平衡逻辑正确（monthly/quarterly/none）
- [ ] 两张表建成功 + task_id 幂等
- [ ] 返回统一 ApiResponse，Swagger 可测

---

## Part B：前端（克隆 MA120 + 组合特色图）

### 1. 页面与表单（克隆 Ma120Backtest.vue）

新建 `frontend/src/views/PortfolioBacktestView.vue`：

| 表单项 | 控件 | 默认 |
|--------|------|------|
| 标的列表 | 多选搜索（多个 ETF，克隆 MA120 搜索，支持累加） | 510880/512890/510300 |
| 模式 | select（fixed/frontier） | fixed |
| 权重（fixed 模式） | 每标的一个 number 输入，显示占比 | 等权 |
| 再平衡频率 | select（monthly/quarterly/none） | monthly |
| 无风险利率 % | number | 2.5 |
| 允许做空 | checkbox（frontier 模式） | false |
| 起止日期 | date | 近 3 年 |
| 「开始回测」 | button.primary | |

- fixed 模式显示权重输入；frontier 模式隐藏权重、显示「允许做空」。

### 2. 图表（三种，克隆 MA120 主题）

#### 2.1 有效前沿图（`EfficientFrontierChart.vue`，frontier 模式核心）

- ECharts scatter：横轴年化波动率(%)、纵轴年化收益(%)。
- **前沿曲线**：连接所有前沿点（smooth line）。
- **单标的点位**：每个标的的 (波动, 收益) 散点，标注名称。
- **等权组合点**：标出。
- **最小方差组合 / 最大夏普组合**：醒目标记（不同色 + label）。
- 点击前沿某点 → 显示该组合的权重配比（联动权重饼图）。

```
收益↑
│            ╭─── 有效前沿
│         ╭──╯        ★ 最大夏普
│      ╭──╯     ●单标的2
│   ╭──╯  ●单标的1
│──╯  ●等权    ○ 最小方差
│  ●单标的3
└──────────────────→ 波动率
```

#### 2.2 净值曲线（`PortfolioNavChart.vue`，fixed 模式 / 与 MA120 同构）

- 组合净值折线 + 等权基准 + 沪深300 基准（归一化）。
- 回撤柱（复用 MA120 的盈亏堆叠柱范式，画 drawdown 序列）。

#### 2.3 相关性热力图（`CorrelationHeatmap.vue`，复用 018 范式）

- ECharts heatmap：标的×标的 相关系数，颜色 -1~+1。

### 3. 指标卡片（克隆 MA120 cards）

| 卡片 | 字段 | 样式 |
|------|------|------|
| 年化收益 | annual_return | pnlColor |
| 年化波动 | annual_volatility | 默认 |
| 夏普比率 | sharpe | pnlColor（>1 优） |
| 最大回撤 | max_drawdown | COLOR_DOWN |
| 总收益 | total_return | pnlColor |

### 4. 权重饼图（辅助）

- ECharts pie：各标的权重占比，颜色区分。
- frontier 模式下随前沿点选择联动变化。

### 5. 路由与导航

- `router/index.ts`：`{ path: '/portfolio', name: 'portfolio', component: PortfolioBacktestView }`
- `App.vue` nav-links：`<RouterLink to="/portfolio">组合回测</RouterLink>`。

### 6. API 封装

`api/index.ts`：`createPortfolio`/`getPortfolioChart`/`getPortfolioSummary` + 类型。

### 验收标准（前端）

- [ ] 导航「组合回测」入口
- [ ] 多标的添加 + 权重输入（fixed 模式）
- [ ] 有效前沿图正确渲染（前沿曲线 + 单标的点 + 最小方差/最大夏普标记）
- [ ] 点击前沿点显示权重配比（联动饼图）
- [ ] 净值曲线（组合 vs 等权 vs 基准）
- [ ] 相关性热力图正确
- [ ] 指标卡片正确（含夏普）
- [ ] 再平衡频率切换重算
- [ ] ?task= 预载可用
- [ ] 明暗主题适配

---

## 数据复用与隔离

| 数据 | 来源 | 复用 |
|------|------|------|
| 多标的行情 | raw_price_daily | ensure_price_data 批量 |
| 协方差/相关性计算 | 新增 portfolio.py | 与 018 相关性计算同源（可后续抽公共） |
| 有效前沿求解 | scipy.optimize | 新依赖 |
| DB/task_id/图表/卡片 | 007 MA120 | 克隆范式 |

> 本任务是**计算复杂度最高**的——多标的对齐、协方差、二次规划都是新代码。建议分两阶段：先 fixed（指定权重），再 frontier（有效前沿）。

---

## 开放问题

- [ ] **风险平价**：让每个标的对组合风险贡献相等（与等权、最小方差并列的优化目标）。
- [ ] **Black-Litterman**：引入用户观点（「我看涨红利」）调整预期收益，进阶组合优化。
- [ ] **再平衡成本**：一期忽略交易成本；后续加手续费/印花税扣除。
- [ ] **滚动有效前沿**：前沿随时间漂移；可画「前沿随时间的变化带」。
- [ ] **与 023 擂台联动**：组合 vs 单标的策略横向对比。
- [ ] **协方差计算抽公共**：与 018 的相关性计算合并到 compute/common。
