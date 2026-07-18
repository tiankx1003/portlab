# 018 — 事件冲击产业链看板（多标的关系网络视角）

## 目标

新增第六个图表页：**事件冲击产业链看板**。从「单标的时间序列」视角跳到「**多标的关系网络 + 事件窗口**」视角，解决「某事件发生后，相关产业链上的股票怎么动、沿什么路径传导」的问题。

**典型场景**：茉莉花产地受灾 → 上游（种植/花农）直接冲击、中游（花茶/香料提取）成本承压、下游（现制茶饮品牌）利润挤压。一眼看清谁受影响、影响多大、传导链路。

**三个视图**（一个页面，层层递进）：

| 视图 | 直观度 | 回答的问题 | 复杂度 |
|------|--------|------------|--------|
| **① 产业链关系图** | 最强（招牌视图） | 谁受影响、沿什么路径传导 | 高（graph 渲染） |
| **② 事件窗口波动对比** | 中（量化） | 事件前后各标的涨跌多少、谁先动 | 低（数据现成） |
| **③ 传导相关性热力图** | 中（深度） | 谁和谁绑得紧、谁是伪概念股 | 中（矩阵计算） |

**核心创新**：之前的图表（回测/资金/估值/回撤）都是「单标的 × 时间」，本页是「**多标的 × 事件 × 关系**」，是全新的形态维度。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)（复用 `raw_price_daily` 行情 + `DataFetcher` 范式）
- [005 — UI 优化与标的信息增强](./005-ui-and-symbol-enhancement.md)（`symbol_catalog.lookup_name`）

> 本任务是迄今最重的：新增「事件 / 主题 / 标的池 / 产业链分组」四个概念层 + graph 渲染 + 相关性计算 + 可选 LLM 依赖。建议分阶段落地（见「落地节奏」）。

---

## Part A：后端

### 1. 数据模型（四个新概念层）

#### 1.1 `event` 表（事件）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT PK | |
| name | VARCHAR(64) NOT NULL | 事件名（如「茉莉花产地受灾」） |
| event_date | DATE NOT NULL | 事件发生日 |
| description | TEXT NULL | 事件描述（可选，供 LLM 匹配） |
| theme_id | INT NULL | 关联的主题模板（FK theme） |
| created_at | DATETIME | |

#### 1.2 `theme` 表（主题模板，可复用的标的池）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT PK | |
| name | VARCHAR(64) NOT NULL | 主题名（如「新茶饮产业链」「香料」） |
| keywords | TEXT NULL | 关键词（供智能匹配，逗号分隔） |
| is_builtin | TINYINT(1) DEFAULT 0 | 是否系统预置 |
| created_at | DATETIME | |

#### 1.3 `theme_stock` 表（主题标的池，含产业链分组）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT PK | |
| theme_id | INT NOT NULL | FK theme |
| symbol | VARCHAR(32) NOT NULL | 标的代码 |
| chain_role | VARCHAR(16) NOT NULL | 产业链角色：`upstream`/`midstream`/`downstream` |
| weight | DECIMAL(5,2) DEFAULT 1.00 | 该标的在环节内权重（相关性/重要性） |
| UNIQUE KEY (theme_id, symbol) | | |

> `chain_role` 是产业链关系图的分组依据——决定节点落在上/中/下游哪个区块。

#### 1.4 `event_stock` 表（事件实例标的池，从主题复制可改）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT PK | |
| event_id | INT NOT NULL | FK event |
| symbol | VARCHAR(32) NOT NULL | |
| chain_role | VARCHAR(16) NOT NULL | |
| UNIQUE KEY (event_id, symbol) | | |

> 设计：创建事件时从 `theme` 复制一份到 `event_stock`，用户可在事件实例上增删而不污染主题模板。

新建 `backend/app/models/event.py`、`theme.py`，在 `models/__init__.py` 注册。

### 2. SQL Migration

- **`mysql/init/08_event_dashboard.sql`**：四张表 + 预置 2~3 个内置主题（如「新茶饮产业链」「香料」「农业种植」）及其成分股（成分股一期可从概念板块拉取后写入，或留空由用户填充）。
- **`mysql/migrations/009_event_dashboard.sql`**：同样四张表，已部署库用。

### 3. 数据拉取（概念板块成分股）

新建 `backend/app/services/fetcher/concept_fetcher.py`：

- `fetch_concept_stocks_em(concept_name) -> list[ConceptStock]`：调 `stock_board_concept_cons_em(symbol=概念名)`，返回成分股代码列表。
- 用于：预置主题时拉成分股、用户选概念板块补全标的池时实时拉取。
- 异常统一抛 `FetchError`。

> akshare 实测：`stock_board_concept_cons_em` 按概念名（如「新茶饮」「香精香料」）返回成分股。茉莉花无专属概念，需组合多个相关概念板块。

### 4. 智能匹配（可选模块，可降级）

新建 `backend/app/services/matcher.py`：

- `smart_match(event_name, description) -> list[MatchedStock]`：
  1. **概念板块匹配**：用关键词扫 akshare 全部概念板块名（`stock_board_concept_em` 列表），返回相关概念及其成分股（确定性、无外部依赖，**基础兜底层**）。
  2. **LLM 增强**（可选）：若配置了 LLM 接入（环境变量 `LLM_API_BASE` / `LLM_API_KEY`），把事件描述 + 候选标的列表喂给 LLM，让它判定产业链角色（上/中/下游）与相关度权重。返回结构化结果。
  3. **降级**：未配置 LLM 时只返回第 1 层结果，`chain_role` 默认置空或全部标 `midstream`，由用户手工调整。

**配置**：
- `backend/app/config.py` 新增：`llm_api_base: str = ""`、`llm_api_key: str = ""`、`llm_model: str = ""`。
- `.env.example` 文档化，留空=禁用智能匹配，退化为概念板块兜底。
- 调用 LLM 属外部请求，注意：事件描述会发送给外部服务，UI 需提示用户。

> **设计原则**：智能匹配是「**增强项**」，不是硬依赖。未配置时任务仍可完整使用（手工建/选主题），保证部署友好。

### 5. 指标计算

新建 `backend/app/services/compute/event_impact.py`：

#### 5.1 事件窗口收益（视图二核心）

```python
def event_window_returns(
    db, symbols: list[str], event_date: date, before: int, after: int
) -> dict[str, list[tuple[date, float]]]:
    """每个标的在 [event_date-before, event_date+after] 的归一化收益序列。
    归一化：event_date 当日收盘 = 0 基准，其余日为累计收益率(%)。
    """
```

- 从 `raw_price_daily` 读，缺失的用 `ensure_price_data` 补拉（复用 002 范式）。
- 返回每标的的 (date, return_pct) 序列，供前端画多曲线。

#### 5.2 事件窗口累计涨跌（视图二排行榜）

```python
def window_cumulative_change(db, symbols, event_date, after) -> dict[str, float]:
    """每标的 event_date → event_date+after 的累计涨跌幅(%)。"""
```

#### 5.3 相关性矩阵（视图三核心）

```python
def correlation_matrix(
    db, symbols, event_date, before, after
) -> list[list[float]]:
    """标的池内日收益率两两皮尔逊相关系数矩阵。"""
```

- 用日收益率 `daily_return = close[t]/close[t-1] - 1`。
- `numpy.corrcoef` 或纯 Python 实现；一期数据量小（几十只标的×几十天），纯 Python 足够。

### 6. Schema

新建 `backend/app/schemas/event_dashboard.py`：

- `EventCreate`：name、event_date、description、theme_id（可选）
- `EventStockUpdate`：symbols 列表（含 symbol、chain_role）
- `SmartMatchRequest`：event_name、description
- `MatchedStock`：symbol、name、chain_role、weight、source（concept/llm）
- `EventImpactData`：
  - `symbols_info[]`：{symbol, name, chain_role}
  - `window_returns{ symbol: { dates[], returns[] } }`（视图二曲线）
  - `ranking[]`：{symbol, name, change_pct, chain_role}（视图二排行榜）
  - `correlation{ symbols[], matrix[][] }`（视图三）
  - `chain_groups`：{upstream: [symbols], midstream: [...], downstream: [...]}（视图一分组）

### 7. API 路由

新建 `backend/app/api/event_dashboard.py`，路由前缀 `/api/event`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/event/themes` | GET | 列出所有主题模板 |
| `/api/event/themes/{id}` | GET | 主题详情含成分股 |
| `/api/event/smart-match` | POST | 智能匹配：输入事件名/描述，返回候选标的（含/不含 LLM） |
| `/api/event/concept-stocks` | GET | 参数 `concept`：实时拉概念板块成分股（补全标的池用） |
| `/api/event` | POST | 创建事件（含标的池，从主题复制或用户提交） |
| `/api/event/{id}` | GET | 事件详情 |
| `/api/event/{id}/stocks` | PUT | 更新事件标的池（增删/调链角色） |
| `/api/event/{id}/impact` | GET | 参数 `before, after`：返回 EventImpactData（三视图合并） |

**业务规则：**
- 所有接口返回统一 `ApiResponse`。
- `smart-match` 未配置 LLM 时退化为概念板块匹配，返回 `source='concept'`；配置了则 `source='llm'`。
- `impact` 接口合并三视图数据一次返回（减少前端并发），内部调三个 compute 函数 + `ensure_price_data` 补数据。
- 创建事件时若传 `theme_id`，从 `theme_stock` 复制到 `event_stock`。

### 8. 路由注册

`backend/app/main.py`：

```python
from .api import ..., event_dashboard, ...
app.include_router(event_dashboard.router, prefix="/api/event", tags=["event"])
```

### 验收标准（后端）

- [ ] 四张概念层表建成功（fresh 走 init/08，已部署走 migrations/009）
- [ ] 内置主题预置成功
- [ ] `stock_board_concept_cons_em` 拉概念板块成分股正常
- [ ] `smart-match` 未配 LLM 时返回概念板块匹配结果（`source='concept'`）；配置时返回 LLM 结果（`source='llm'`）
- [ ] 事件窗口收益归一化正确（事件日=0 基准）
- [ ] 相关性矩阵对称、对角线=1
- [ ] 创建事件从主题复制标的池成功；事件实例增删不影响主题模板
- [ ] `impact` 接口合并三视图数据返回，字段完整
- [ ] 行情缺失时 `ensure_price_data` 补拉
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. API 封装

`frontend/src/api/index.ts` 新增：

- `listThemes()`、`getTheme(id)`
- `smartMatch(body)`、`listConceptStocks(concept)`
- `createEvent(body)`、`getEvent(id)`、`updateEventStocks(id, body)`
- `getEventImpact(id, params)`
- 对应 TypeScript 类型 `Theme`、`EventStock`、`MatchedStock`、`EventImpactData`

### 2. 路由与导航

- `router/index.ts` 新增 `{ path: '/event', name: 'event', component: EventDashboardView }`
- `App.vue` `nav-links` 新增 `<RouterLink to="/event">事件看板</RouterLink>`，排在「估值看板」之后。

### 3. 页面（`frontend/src/views/EventDashboardView.vue`）

**布局：**

```
┌─────────────────────────────────────────────────────┐
│  事件冲击产业链看板                                  │
│  [事件名输入] [事件日期] [描述] [智能匹配] [新建事件]│  ← 事件输入
│  [选主题▼] [选概念补全▼] [标的池表格: 代码/名称/角色]│  ← 标的池管理
│  [窗口: 事件前 N天 ▼] [事件后 M天 ▼] [查询]         │  ← 窗口控制
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐    │
│  │     视图① 产业链关系图（上→中→下游）         │    │  ← 招牌视图
│  │  [上游]●XX +12% → [中游]●XX -3% → [下游]●XX │    │
│  └─────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐    │
│  │  视图② 事件窗口波动对比（多归一化曲线）      │    │
│  │  事件日=0基准，多股叠加 + 涨跌排行榜         │    │
│  └─────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐    │
│  │  视图③ 相关性热力图（标的×标的）             │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

### 4. 事件输入与标的池管理（上半区）

- **事件输入**：事件名 + 日期 + 描述（描述供智能匹配用）。
- **智能匹配按钮**：调 `/api/event/smart-match`，返回候选标的列表（含链角色），用户勾选确认。**若后端未配 LLM，UI 提示「使用概念板块匹配（如需更精准可配置 LLM）」**。
- **主题/概念补全**：选内置主题一键载入标的池；或选概念板块实时拉成分股补全。
- **标的池表格**：列出当前事件标的，每行可编辑 `chain_role`（上/中/下游下拉）、删除、添加。表格是标的池的真相源。

### 5. 视图①：产业链关系图（`EventChainGraph.vue`）

**库选择**：用 **ECharts `graph`** 系列（项目已依赖 echarts，不引新库；若布局复杂度超出 graph 能力，二期再评估 AntV G6）。

- **节点**：每个标的一个圆点，按 `chain_role` 分到上/中/下游三个区块（用 ECharts `categories` + 力引导或固定布局）。
- **节点颜色**：事件窗口涨跌幅映射（红涨绿跌，复用 COLOR_UP/DOWN）。
- **节点大小**：映射波动幅度（涨跌绝对值越大越大）。
- **连线**：上→中→下游传导方向（箭头）；可选标注相关性（高相关=粗线）。
- **点击节点**：高亮该标在视图②③中的对应曲线/行列（三图联动，一期可选）。
- 复用主题色 `themeColors()`，dataZoom 不需要（非时间轴）。

### 6. 视图②：事件窗口波动对比（`EventImpactChart.vue`）

**克隆 `Ma120Chart.vue` 范式**：

- 横轴：日期（事件前 N → 事件日 → 事件后 M）。
- 纵轴：归一化收益率(%)，事件日 = 0 基准线（`markLine` 强调）。
- 每只标的一条折线（颜色区分），事件日加 `markLine`（垂直虚线「事件日」）。
- 叠加沪深300 基准线（虚线，对照大盘）。
- tooltip：日期 + 各标的当日累计收益。
- 右侧/下方配**涨跌排行榜表格**：symbol、name、chain_role、事件窗口累计 change_pct，按涨跌排序，链角色用 chip 标色。
- dataZoom、setOption(true)、resize、watch(theme) 照搬。

### 7. 视图③：相关性热力图（`CorrelationHeatmap.vue`）

- ECharts `heatmap` 系列：标的×标的 矩阵，颜色映射 -1~+1（蓝=负相关、白=0、红=正相关，或复用冷热配色）。
- 对角线 = 1（自相关）。
- 行列标注 symbol/name（缩写或代码）。
- tooltip：A 与 B 的相关系数。
- 用于发现「伪概念股」（被分进板块但相关性低）和隐藏传导链（高相关但跨环节）。

### 8. 交互细节

- 窗口 N/M 调整 → 重新查 `/impact`，三视图联动刷新。
- 三图联动（一期可选）：点关系图节点 → 高亮波动曲线 + 热力图行列。
- 标的池变更 → 保存后重新查 `/impact`。
- 空态：无事件/无标的/无行情各自提示。

### 验收标准（前端）

- [ ] 导航新增「事件看板」入口
- [ ] 事件输入 + 智能匹配可用；未配 LLM 时降级提示正确
- [ ] 主题/概念补全标的池可用
- [ ] 标的池表格可增删改链角色
- [ ] 视图①：节点按上/中/下游分组，颜色映射涨跌，点击高亮
- [ ] 视图②：多归一化曲线 + 事件日基准线 + 排行榜表格
- [ ] 视图③：相关性热力图正确渲染，对角线=1
- [ ] 窗口 N/M 调整三图联动
- [ ] 明暗主题切换后样式正确
- [ ] 复用 Ma120Chart 范式与 CSS 变量

---

## 数据复用与隔离策略

| 数据 | 来源 | 复用/隔离 |
|------|------|-----------|
| 个股行情 | `raw_price_daily`（已有） | `ensure_price_data` 补拉 |
| 概念板块成分股 | akshare `stock_board_concept_cons_em` | 实时拉取，不入库（或缓存） |
| 事件/主题/标的池 | 四张新表 | 独立概念层，与行情隔离 |
| 智能匹配 | akshare 概念 + 可选 LLM | 可降级，非硬依赖 |

> 行情数据完全复用现有表；事件/主题是新增的概念层，独立建表。

---

## 落地节奏（重要：本任务最重，建议分阶段）

本任务范围远大于其他图表，建议**分三阶段**，每阶段可独立上线：

**阶段一：波动对比看板（核心可用）**
- 后端：四张表 + 事件/主题/标的池 CRUD + `event_window_returns` + `window_cumulative_change`。
- 前端：事件输入 + 标的池管理（先靠选主题/概念补全，**不含智能匹配**）+ 视图②。
- 价值：立刻能回答「受灾后相关股涨跌多少」核心问题。数据零新增（用现有行情表）。

**阶段二：产业链关系图 + 相关性热力图**
- 后端：`correlation_matrix` + `chain_groups`。
- 前端：视图①（ECharts graph）+ 视图③（heatmap）+ 三图联动。
- 价值：体验炸裂，补齐关系维度。

**阶段三：智能匹配（可选增强）**
- 后端：`smart_match`（概念板块兜底 + LLM 增强）+ LLM 配置项。
- 前端：智能匹配按钮 + 降级提示。
- 价值：解决「朋友不知道有哪些股」的真问题；未配置不影响前两阶段。

---

## 开放问题（后续迭代）

- [ ] **graph 库评估**：一期 ECharts `graph`；若产业链层级多/布局复杂，二期评估 AntV G6。
- [ ] **概念板块缓存**：`stock_board_concept_cons_em` 实时拉取有限频，可加进程缓存。
- [ ] **LLM 接入**：一期留接口未实现；二期接具体 LLM（OpenAI 兼容/国产），含成本与隐私提示。
- [ ] **传导强度量化**：一期连线静态；二期用 Granger 因果或领先滞后相关量化传导方向与强度。
- [ ] **历史事件库**：预置经典事件（如过往自然灾害、政策事件）供回放研究。
- [ ] **产业链模板库**：扩充预置主题（新能源/半导体/消费等常见产业链），降低用户建池成本。
- [ ] **与估值/回测联动**：选中标的可一键跳转估值看板/回测，形成「事件发现标的 → 深度分析」链路。
