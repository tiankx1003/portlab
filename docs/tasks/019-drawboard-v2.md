# 019 — drawboard v2：补齐 sell_mode + DB 持久化 + 参数纠正

## 目标

对 [015](./015-drawdown-buy-strategy.md) 已交付的「回撤看板」（drawboard）做系统性补齐。v1 是可用的 MVP，但与设计/用户初衷存在多项偏离，本任务逐项修正：

**功能补齐：**
1. **补 sell_mode 开关**（核心）——v1 硬编码「新高清仓」，无法只买不卖。补 none/new_high/partial 三模式，**默认 new_high**（保留 v1 当前行为，平滑过渡），新增 none 回到用户最初设想。
2. **补 DB 持久化 + task_id 幂等**——v1 无状态每次重算，结果无法被首页「最近记录」引用。镜像 MA120 范式建两张表。
3. **纠正参数默认值**——v1 threshold=10/step=2/add_amount=10000/起始写死 2022，对齐 015 设计值。
4. **命名统一**——已在 015 文档侧完成（drawdown→drawboard），代码侧无需改动（代码本就是 drawboard）。本项仅记录。

**UI/交互全面对齐 MA120 看板（本任务新增重点）：**
5. **回撤阈值改为输入框**（v1 是滑块 `<input type="range">`），改为 `<input type="number">`，与 MA120 的 `买入阈值`/`加仓步长` 同款 number 输入。
6. **表单与按钮布局克隆 MA120**——`.form-card` + `.form-row`（两行布局）+ 高级参数折叠 + `button.primary`，直接复用 MA120 的 CSS 结构与 class 名。
7. **指标卡片克隆 MA120**——含 `买卖次数` 合并卡（红买/蓝卖 + 胜率样式），与 MA120 完全一致。
8. **图表 tooltip / 买卖点 / 图例克隆 MA120**——`Ma120Chart.vue` 的 markPoint（pin 红/蓝）、legend、tooltip formatter（📌 信号 + 内联色明细）整体复用。

**交互形态**（关键决策）：采用**实时 GET + 保存落库**双轨——
- 改参数后点「开始回测」→ `GET /api/drawboard/backtest` 实时重算（保持 v1 快速响应，无 task_id）。
- 点「保存」按钮 → `POST /api/drawboard/save` 落库生成 task_id（供 011 首页最近记录、012 直达链接消费）。

这样既保持快速响应，又让结果进入持久化体系。

## 依赖

- [015 — 基于最大回撤的买入策略看板](./015-drawdown-buy-strategy.md)（本任务是其 v1 的迭代）
- [003 — 定投回测](./003-dca-compute-engine.md)（`annualized_return`/`xirr`/`max_drawdown` 公共函数复用）
- [007 — 红利 MA120 策略回测](./007-ma120-strategy-backtest.md)（**DB 持久化、task_id 幂等、sell_mode 分支的范式模板**）
- [011 — 首页改版](./011-home-redesign.md)（最近回测记录消费 task_id）
- [012 — 回测结果直达](./012-backtest-deeplink.md)（`?task=` 预载消费 task_id）

> 本任务是纯增量修正，不破坏 v1 现有 API（`GET /backtest`、`GET /series` 保留）。

---

## v1 偏离基线（本任务修正起点）

详见 [015 实现偏离记录](./015-drawdown-buy-strategy.md#实现偏离记录v1-交付物快照2026-07-评审)。摘要：

| 偏离 | v1 状态 | 本任务目标 |
|------|---------|-----------|
| sell_mode | 硬编码 new_high | 三模式开关，默认 new_high |
| DB 持久化 | 无 | 两张表（镜像 MA120） |
| task_id 幂等 | 无 | make_task_id 命中缓存 |
| 参数默认值 | threshold10/step2/add10000/2022固定 | threshold20/step5/add5000/近3年 |
| annualized_return | 未算 | 复用 common |
| max_drawdown | 未算（虽有滚动序列） | 复用 common |
| benchmark 重复定义 | 本地常量 | 导入 benchmark.py |

---

## Part A：后端

### 1. sell_mode 引擎分支（核心）

改 `backend/app/services/drawboard.py` 的 `_simulate()` 卖出块（v1 约第 111-117 行）：

```python
# v1 现状（硬编码 new_high）：
if holding > 0 and dd >= 0:
    proceeds = holding * price
    cum_proceeds += proceeds
    sells.append(...)
    holding = Decimal(0)
    last_buy_dd = None
```

改为按 `sell_mode` 分支：

```python
if holding > 0 and dd >= 0:
    if sell_mode == "none":
        pass  # 不卖，只买不卖（用户最初设想）
    elif sell_mode == "new_high":
        proceeds = holding * price            # 全清
        cum_proceeds += proceeds
        sells.append({"date": d, "price": float(price), "amount": float(proceeds)})
        holding = Decimal(0)
        last_buy_dd = None                    # 重置买入阶梯
    elif sell_mode == "partial":
        sell_shares = holding / 2             # 卖一半，留底仓
        proceeds = sell_shares * price
        cum_proceeds += proceeds
        sells.append({"date": d, "price": float(price), "amount": float(proceeds)})
        holding -= sell_shares
        # 不重置 last_buy_dd，下次跌破仍可加仓
```

**签名扩展**：`_simulate(...)` 与 `run_drawdown_backtest(...)` 加 `sell_mode: str = "new_high"` 参数。

**模式语义**：
| 模式 | 行为 | 适用场景 |
|------|------|----------|
| `none` | 只买不卖，`cum_proceeds` 恒 0，`mv = holding × price` | 用户最初设想：持仓展示收益率 |
| `new_high`（默认） | dd≥0 清仓 + 重置阶梯 | v1 行为，波段兑现 |
| `partial` | dd≥0 卖一半，留底仓，不重置阶梯 | 留底仓等下次跌破再买 |

### 2. DB 持久化（镜像 MA120）

#### 2.1 新表 `calc_drawboard_backtest`（逐日）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | 任务 ID |
| trade_date | DATE PK | 交易日 |
| signal | VARCHAR(8) | buy/sell/hold |
| action_amount | DECIMAL(18,2) | 当日操作金额 |
| holding | DECIMAL(20,8) | 持仓份额 |
| cum_invested | DECIMAL(18,2) | 累计投入 |
| cum_proceeds | DECIMAL(18,2) | 累计套现（卖出回款） |
| market_value | DECIMAL(18,2) | 当日市值（holding×price + cum_proceeds） |
| pnl | DECIMAL(18,2) | 盈亏 = mv − cum_invested |
| return_rate | DECIMAL(12,4) | 收益率(%) |
| drawdown | DECIMAL(8,4) | 当日滚动回撤(%)，负值 |
| close | DECIMAL(14,4) | 当日收盘（冗余） |
| KEY idx_task (task_id) | | |

#### 2.2 新表 `result_drawboard_summary`（汇总）

| 字段 | 类型 | 说明 |
|------|------|------|
| task_id | VARCHAR(96) PK | |
| symbol | VARCHAR(32) | |
| sell_mode | VARCHAR(8) | none/new_high/partial |
| threshold | DECIMAL(8,4) | 回撤阈值 |
| step | DECIMAL(8,4) | 加仓步长 |
| buy_amount | DECIMAL(18,2) | 首笔金额 |
| add_amount | DECIMAL(18,2) | 加仓金额 |
| start_date / end_date | DATE | |
| total_invested | DECIMAL(18,2) | |
| final_value | DECIMAL(18,2) | |
| total_pnl | DECIMAL(18,2) | |
| total_return_rate | DECIMAL(12,4) | |
| annualized_return | DECIMAL(12,4) | **新增**（v1 缺） |
| max_drawdown | DECIMAL(12,4) | **新增**（v1 缺） |
| buy_count | INT | |
| sell_count | INT | |
| KEY idx_symbol (symbol) | | |

> 表结构对齐 MA120（`init/01_schema.sql` 的 calc_ma120/result_ma120），命名 drawboard。

#### 2.3 ORM 与 SQL

- 新建 `backend/app/models/drawboard.py`（`CalcDrawboardBacktest` + `ResultDrawboardSummary`），注册到 `models/__init__.py`。
- `mysql/init/0X_drawboard.sql`（fresh）：两张表 `CREATE TABLE IF NOT EXISTS`。
- `mysql/migrations/0XX_drawboard.sql`（已部署）：同样两张表，文件头写明「fresh 已由 init 包含」。
- 编号待定时按 `mysql/init/` 与 `mysql/migrations/` 当前最大号 +1（实施时确认）。

### 3. task_id 幂等（镜像 MA120 make_task_id）

```python
def make_task_id(symbol, start, end, threshold, step, buy_amount, add_amount, sell_mode, source):
    base = (f"db_{symbol}_{start:%Y%m%d}_{end:%Y%m%d}"
            f"_{threshold}_{step}_{buy_amount}_{add_amount}_{sell_mode}")
    return f"{base}_{source}" if source != "akshare" else base
```

- 全参数确定性；非 akshare 源追加 `_{source}` 后缀（与 MA120/DCA 一致）。
- `POST /save` 先 `db.get(ResultDrawboardSummary, task_id)`，命中则直接返回，不重算。

### 4. 补 annualized_return 与 max_drawdown（复用公共函数）

`run_drawdown_backtest` 汇总段补：

```python
from .compute.common import annualized_return, max_drawdown
# cashflows: 每次买入为负现金流（-amount, date），最终市值归位为正（final_value, end_date）
annualized = annualized_return(cashflows, total_return_rate, dates)
mdd = max_drawdown(market_values)   # market_values 序列
```

- v1 已有 `market_values` 序列，`max_drawdown` 直接套用。
- cashflows 需按买入记录 + 终值构造（参考 MA120 `ma120.py:304-339`）。

### 5. benchmark 复用

`drawboard.py:20` 的 `BENCHMARK_SYMBOL = "510300"` 本地常量 → 改为从 `services/benchmark.py` 导入：

```python
from .benchmark import BENCHMARK_SYMBOL  # 消除重复定义
```

### 6. Schema 扩展（`schemas/drawboard.py`）

- 新增 `DrawboardRequest`：
  ```python
  class DrawboardRequest(BaseModel):
      symbol: str
      start_date: date
      end_date: date
      threshold: float = Field(20.0, gt=0)
      step: float = Field(5.0, gt=0)
      buy_amount: float = Field(10000.0, gt=0)
      add_amount: float = Field(5000.0, gt=0)
      sell_mode: Literal["none", "new_high", "partial"] = "new_high"
  ```
- `DrawSummary` 加字段：`annualized_return: float`、`max_drawdown: float`、`sell_mode: str`。
- 新增 `DrawboardSaved`：`task_id: str`。

### 7. API（`api/drawboard.py`）——双轨：保留实时 GET + 新增落库三接口

| 接口 | 方法 | 说明 | 状态 |
|------|------|------|------|
| `/api/drawboard/series` | GET | 行情 + 回撤序列（图表底图） | v1 保留 |
| `/api/drawboard/backtest` | GET | **实时重算**（加 sell_mode 参数，无 task_id） | v1 改造（加 sell_mode + 新默认值） |
| `/api/drawboard/save` | POST | 提交参数 → 命中缓存或计算 → 落库 → 返回 task_id | **新增** |
| `/api/drawboard/{task_id}/chart` | GET | 读 calc_drawboard_backtest 逐日 | **新增** |
| `/api/drawboard/{task_id}/summary` | GET | 读 result_drawboard_summary 汇总 | **新增** |

**业务规则：**
- `GET /backtest`：参数默认值改为 threshold=20/step=5/add_amount=5000（纠正），加 `sell_mode` 参数默认 new_high。**每次重算不落库**，供拖滑块松手快速响应。
- `POST /save`：参数同上，`make_task_id` → 命中 `result_drawboard_summary` 则直接返回 task_id；否则 `ensure_price_data` 补数据 → 计算 → 写两张表 → 返回 task_id。
- `GET /{task_id}/chart` 与 `/summary`：从表读，返回结构与实时 GET 一致（前端无感）。
- 返回统一 `ApiResponse`。

### 8. 参数默认值纠正

| 参数 | v1 | v2（对齐 015 设计） |
|------|----|----|
| threshold | 10.0 | **20.0** |
| step | 2.0 | **5.0** |
| buy_amount | 10000.0 | 10000.0（保留） |
| add_amount | 10000.0 | **5000.0** |
| 起始日期 | 写死 2022-01-01 | 动态近 3 年（前端算，后端不强制） |
| sell_mode | 硬编码 new_high | 参数化，**默认 new_high**（保留 v1 行为） |

> sell_mode 默认值刻意保留 new_high 而非 015 文档的 none——避免改变 v1 用户的既有体验，none/partial 作为可选。

### 路由注册

`backend/app/main.py`：drawboard 路由已注册（`/api/drawboard`），新增接口自动挂载，无需改 main.py。

### 验收标准（后端）

- [ ] sell_mode 三分支正确：none 不卖（cum_proceeds 恒 0）；new_high 全清+重置；partial 卖一半+不重置
- [ ] `calc_drawboard_backtest` + `result_drawboard_summary` 两张表建成功（fresh + migration）
- [ ] `make_task_id` 全参数确定性；非 akshare 源追加后缀
- [ ] `POST /save` 命中缓存返回旧 task_id，不重算
- [ ] `annualized_return` 正确计算（XIRR 优先，无解回退）
- [ ] `max_drawdown` 正确（套用 market_values 序列）
- [ ] `GET /backtest` 默认值已纠正（threshold20/step5/add5000），加 sell_mode 参数
- [ ] `benchmark` 从 `services/benchmark.py` 导入，无本地重复
- [ ] 实时 GET 与落库 POST 都可用，返回结构一致
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端（全面对齐 MA120 看板）

> **总原则**：v1 的 `DrawboardView.vue` 是滑块+内联图表的简化形态。本任务**整体克隆 `Ma120Backtest.vue` + `Ma120Chart.vue` 范式**重构，使回撤看板与 MA120 看板在表单、卡片、图表、tooltip 上视觉与交互完全一致。下方逐项给出 MA120 的精确模板（文件:行），实施时直接对照复刻。

### 1. 表单布局克隆 MA120（含阈值改输入框）

**模板参照** `Ma120Backtest.vue:222-325`：`.form-card` 包裹，内含两行 `.form-row` + 高级参数折叠区。

回撤看板的表单项映射（参照 MA120 的 label + input/select 结构）：

```
.form-card
├─ .form-row（第一行）
│  ├─ 标的代码（symbol-field + 搜索 datalist，复用 MA120:224-238 的搜索去抖逻辑）
│  ├─ 卖出方式 <select>（new_high/none/partial，默认 new_high）
│  ├─ 首笔金额 <input type=number>（buy_amount，默认 10000）
│  └─ 加仓金额 <input type=number>（add_amount，默认 5000）
├─ .form-row（第二行）
│  ├─ 起始日期 <input type=date>
│  ├─ 结束日期 <input type=date>
│  ├─ 回撤阈值 <input type=number>（threshold，默认 20）← 原 v1 滑块，改为输入框
│  ├─ 加仓步长 <input type=number class="narrow">（step，默认 5）
│  ├─ <button class="primary">开始回测</button>  ← 触发 GET /backtest 实时重算
│  └─ <button class="primary">保存</button>      ← 触发 POST /save 落库
└─ .advanced（可折叠，本任务暂无高级项，预留）
```

**关键变化**：
- **回撤阈值**：v1 `<input type="range" min=3 max=50>`（`DrawboardView.vue:205`）→ 改为 `<input type="number" min="1" max="80" step="1">`，与 MA120 的「买入阈值」`Ma120Backtest.vue:304` 同款。
- **触发方式**：v1 用 watch 监听滑块松手自动重算 → 改为 MA120 的「开始回测」按钮显式触发（`runBacktest()`，`Ma120Backtest.vue:291-293`）。watch 自动重算移除，避免输入过程中频繁请求。
- **样式**：直接复用 MA120 的 `.form-card`/`.form-row`/`label`/`input`/`select`/`button.primary`/`.advanced*` 全部 CSS（`Ma120Backtest.vue:365-519`），拷贝到 `DrawboardView.vue` 的 `<style scoped>`。
- 标的搜索：复用 MA120 的 `onSymbolInput` 去抖 + `detectMarket` + `symbolHint`（`Ma120Backtest.vue:54-95`），让回撤看板也有代码补全与市场识别。

### 2. 指标卡片克隆 MA120

**模板参照** `Ma120Backtest.vue:330-355`：`.cards` flex 行 + `MetricCard` 组件 + 一个合并的 `买卖次数` 卡。

回撤看板卡片（参照 MA120 顺序与样式）：

| 卡片 | 字段 | 样式 |
|------|------|------|
| 累计投入 | `total_invested` | 默认 |
| 当前市值 | `final_value` | 默认 |
| 累计收益 | `total_pnl` | `pnlColor`（红/绿） |
| 累计收益率 | `total_return_rate` + '%' | `pnlColor` |
| 年化收益率 | `annualized_return` + '%' | `pnlColor`（**新增**） |
| 最大回撤 | `max_drawdown` + '%' | `COLOR_DOWN` 绿（**新增**） |
| **买卖次数** | 合并卡：`buy_count` / `sell_count` | **克隆 MA120 的 `.trade-card`**（`Ma120Backtest.vue:345-353` + CSS 460-500） |

**买卖次数合并卡**（重点克隆）—— MA120 用红买/蓝卖双色 + 胜率小字，回撤看板无胜率（策略性质不同），改为「买卖次数 + 持仓周期数」或仅买卖次数：

```html
<div class="trade-card">
  <div class="tc-label">买卖次数</div>
  <div class="trade-value">
    <span class="num-buy">{{ summary.buy_count }}</span>
    <span class="sep">/</span>
    <span class="num-sell">{{ summary.sell_count }}</span>
  </div>
</div>
```

- `.num-buy { color:#ee6666 }`（红，与图表买入标记一致）
- `.num-sell { color:#3a7afe }`（蓝，与图表卖出标记一致）
- 完整 CSS 照搬 `Ma120Backtest.vue:460-500`。

> MA120 还有「分红累计」卡，回撤看板无分红概念，**不复制**。

### 3. 图表组件克隆 Ma120Chart（tooltip/买卖点/图例）

**新建独立组件** `frontend/src/components/DrawboardChart.vue`，**克隆 `Ma120Chart.vue` 全文结构**，按下述差异适配。v1 是内联于 View 的 echarts，本任务拆成独立组件（与 MA120 一致）。

**直接复用（照搬 Ma120Chart.vue）**：
- 生命周期（`Ma120Chart.vue:206-231`）：`render()` → `setOption(opt, true)` 全量替换、`onResize`、`onMounted` init、`onBeforeUnmount` dispose、`watch(props.data)` + `watch(theme)`。
- `themeColors()`（`Ma120Chart.vue:22-32`）：明暗主题调色板原样复用。
- 配色常量（`Ma120Chart.vue:8-15`）：`COLOR_UP`/`COLOR_DOWN`/`COLOR_BENCH`/`COLOR_BUY`/`COLOR_SELL` 原样复用（红买蓝卖）。
- `legend`（`:165`）：`top:0`、`textStyle.color: tc.axisLabel`。
- `grid`（`:166`）：`{ left:64, right:120, top:40, bottom:64 }`。
- `dataZoom`（`:198-201`）：inside + slider。
- `LegendHint` 组件（`:236`）。

**买卖点 markPoint（克隆 `Ma120Chart.vue:40-57, 90-95`）**：

```ts
const buyMarks = d.buy_points.map(p => ({
  name:'买入', coord:[p.date, p.price], value:'买',
  itemStyle:{color:COLOR_BUY}, symbol:'pin', symbolSize:38,
  label:{color:'#fff', fontSize:10, fontWeight:700}
}))
const sellMarks = d.sell_points.map(p => ({
  name:'卖出', coord:[p.date, p.price], value:'卖',
  itemStyle:{color:COLOR_SELL}, symbol:'pin', symbolSize:38,
  label:{color:'#fff', fontSize:10, fontWeight:700}
}))
// 落在收盘价线上
markPoint: { symbol:'pin', symbolSize:38, data:[...buyMarks, ...sellMarks], label:{fontSize:10} }
```

- pin 标、symbolSize 38、红买（#ee6666）蓝卖（#3a7afe）——与 MA120 **完全一致**。

**tooltip formatter（克隆 `Ma120Chart.vue:122-163` 的风格与结构）**：

`trigger:'axis'` + `axisPointer:{type:'cross'}` + 自定义 formatter 返回 HTML 字符串，内联色 span。回撤看板的当日明细项（替换 MA120 的 MA/偏离为回撤）：

```ts
formatter: (params) => {
  const i = params[0].dataIndex
  const sig = d.signals[i]
  const sigColor = sig==='buy' ? COLOR_BUY : sig==='sell' ? COLOR_SELL : tc.axisLabel
  // ... 取 close/drawdown/mv/pnl/rate/bench
  return (
    `${d.dates[i]}` +
    (sig!=='hold' ? `　<span style="color:${sigColor};font-weight:600">📌 ${SIGNAL_LABEL[sig]}</span>` : '') +
    (amt!=null ? `<br/>${amtLabel}：<span style="color:${sigColor};font-weight:600">${amt}</span>` : '') +
    `<br/>价格：${f2(close)}` +
    `<br/>回撤：<span style="color:${COLOR_DOWN}">${f2(drawdown)}%</span>　阈值：<span>${threshold}%</span>` +
    `<br/>持仓：${f2(hold)}` +
    `<br/>市值：${f2(mv)}　成本：${f2(cost)}` +
    `<br/>盈亏：<span style="color:${pnlColor};font-weight:600">${pnl>=0?'+':''}${f2(pnl)}</span>` +
    `　收益率：<span style="color:${rateColor};font-weight:600">${f2(rate)}%</span>` +
    (hasBench ? `<br/>${benchName}：<span style="color:${COLOR_BENCH}">${f2(bench)}%</span>` : '')
  )
}
```

- 风格完全对齐 MA120：📌 信号标、内联色、金额千分位、盈亏带 +/-、收益率带 %。
- 差异项：MA120 的「MA120/偏离」→ 换成「回撤/阈值」。

**图例 legend（对齐 MA120）**：

```ts
legendData = ['市值','成本','亏损','盈利','收益率','收盘价','回撤']
// hasBench 时 push benchmark_name
```

- 与 MA120 的 `['市值','成本','亏损','盈利','收益率','收盘价','MA120']` 同构，仅把 MA120 换成「回撤」。

**series 结构（对齐 MA120 的双轴 + 堆叠柱）**：

| series | 类型 | 轴 | 说明 |
|--------|------|----|----|
| 市值 | line | 左轴(金额) | 主色 #5470c6 |
| 成本 | line dashed | 左轴 | 灰 #9aa4b2 |
| 亏损 | bar stack:'pnl' | 左轴 | COLOR_DOWN（v<0） |
| 盈利 | bar stack:'pnl' | 左轴 | COLOR_UP（v≥0） |
| 收益率 | line | 右轴1(%) | 橙 #ee9c2a |
| 收益价 | line | 右轴2(价格) | 浅蓝 COLOR_CLOSE，**带 markPoint 买卖点** |
| 回撤 | line | 右轴2 或独立 | 替代 MA120 的 MA 线 |
| 基准（可选） | line dotted | 右轴1 | COLOR_BENCH |

> 注：v1 用「单轴中间 0 线镜像」画价格/回撤；本任务**改为 MA120 的三轴范式**（金额/收益率/价格各一轴），回撤作为一条附加 line。这样与 MA120 视觉完全统一，放弃 015 原设计的镜像轴（那只是 v1 草稿设想，未实际带来更好体验）。

### 4. sell_mode 选择器与提示文案

sell_mode `<select>` 已在 §1 表单中。提示文案动态化（v1 写死「新高清仓」）：

```ts
const sellHint = computed(() => ({
  none: '只买不卖，持仓展示收益率',
  new_high: '新高（回撤归 0）清仓兑现',
  partial: '新高卖出 50%，留底仓等下次跌破再买',
}[sellMode.value]))
```

放在表单底部 `.muted` 段（替代 v1 `DrawboardView.vue:180-182` 的写死文案）。

### 5. 「保存」按钮与 ?task= 预载

- **保存按钮**（§1 表单第二行）：调 `saveDrawboard(params)` → POST `/save` → 返回 task_id → toast 提示「已保存，可从首页最近记录查看」。成功后该结果可被 011 首页最近记录、012 `?task=` 直达消费。
- **?task= 预载**（对齐 MA120 的 `loadTask`，`Ma120Backtest.vue:156-194`）：`onMounted` 读 `route.query.task`，调 `getDrawboardChart` + `getDrawboardSummary` 直载结果并回填表单。需配套 `parseDrawboardTaskId` 工具函数（解析 `db_{symbol}_{start}_{end}_...` 格式，参照 MA120 的 `utils/taskId.ts`）。

### 6. API 封装（`api/index.ts`）

新增/修改：
- `saveDrawboard(params)` → POST `/api/drawboard/save`
- `getDrawboardChart(taskId)` → GET `/api/drawboard/{id}/chart`
- `getDrawboardSummary(taskId)` → GET `/api/drawboard/{id}/summary`
- `runDrawdownBacktest(params)` 参数加 `sell_mode`
- `DrawSummary` 类型加 `annualized_return`、`max_drawdown`、`sell_mode` 字段
- `DrawBacktestResult` 加 `signals: string[]`、`holding: number[]`、`total_cost: number[]`、`pnl: number[]`、`close_prices: number[]`、`benchmark_returns: number[]`、`benchmark_name: string`、`symbol_name: string`（对齐 `Ma120ChartData` 结构，供图表克隆用）

> 后端 `DrawBacktestResult` schema 需相应补齐上述字段（Part A §6 已含 chart data 字段，此处强调与 Ma120ChartData 同构）。

### 验收标准（前端）

- [ ] **回撤阈值为输入框**（number），非滑块
- [ ] 表单布局与 MA120 一致（`.form-card` + 两行 `.form-row` + 折叠高级区 + `button.primary`）
- [ ] 标的搜索去抖 + 市场识别可用（克隆 MA120）
- [ ] 「开始回测」按钮显式触发（非 watch 自动重算）
- [ ] 指标卡片含「买卖次数」合并卡（红买蓝卖，克隆 MA120 `.trade-card`）
- [ ] 年化收益率、最大回撤卡片数据正确
- [ ] **图表独立组件 `DrawboardChart.vue`**，结构与 Ma120Chart 一致
- [ ] 买卖点 markPoint：pin 红/蓝，symbolSize 38，与 MA120 一致
- [ ] tooltip：📌 信号 + 内联色明细（回撤/阈值 替代 MA/偏离），风格与 MA120 一致
- [ ] 图例与 MA120 同构（市值/成本/盈亏/收益率/收盘价/回撤/基准）
- [ ] series 三轴 + 堆叠柱（盈/亏分色），与 MA120 一致
- [ ] sell_mode 单选默认 new_high，提示文案随模式变
- [ ] 「保存」按钮调 POST 落库返回 task_id
- [ ] `?task=` 预载可用（克隆 MA120 loadTask）
- [ ] 默认值已纠正（threshold20/step5/add5000/近3年）
- [ ] 明暗主题切换后样式正确

---

## 数据复用与隔离策略

| 数据 | 来源 | 复用方式 |
|------|------|----------|
| 行情 | `raw_price_daily` | `ensure_price_data` 补拉 |
| 基准 | `services/benchmark.py` | 导入 BENCHMARK_SYMBOL（消除 v1 重复） |
| annualized/max_drawdown | `compute/common.py` | 公共函数复用（v1 缺，本任务补） |
| DB 持久化范式 | 007 MA120 | 镜像 calc/result 两表 + task_id |
| sell_mode 分支范式 | 007 MA120 sell_mode | 同构（none/new_high/partial vs batch/all/half） |
| 前端表单/卡片/图表/tooltip | `Ma120Backtest.vue` + `Ma120Chart.vue` | **整体克隆**，本任务 UI 对齐的核心 |

> 本任务几乎不新建数据/逻辑——sell_mode 分支、两表结构、task_id、annualized/max_drawdown、前端全套 UI 均镜像 MA120 既有实现，是低风险的增量补齐。

---

## 开放问题（后续迭代）

- [ ] **sell_mode 是否加 batch**：MA120 有 batch（分批卖出），drawboard 是否需要「新高后分批卖出」而非全清/半仓。
- [ ] **实时 GET 是否命中缓存**：当前实时 GET 每次重算；可改造为先查 `result_drawboard_summary` 命中则直接返回（与 POST /save 同源），减少重复计算。
- [ ] **参数默认值 A/B**：v1 值（10/2/10000）vs 015 设计值（20/5/5000）哪个实际回测更优，可数据验证后再定。
- [ ] **rolling_drawdown 抽公共函数**：v1 内联于 service；可抽到 `compute/common.py` 供未来其他回撤类功能复用。
- [ ] **回撤轴的镜像布局**：本任务统一为 MA120 三轴范式（放弃 015 草稿的「单轴 0 线镜像」）；若未来想突出「价格与回撤镜像」的视觉，可再评估。
