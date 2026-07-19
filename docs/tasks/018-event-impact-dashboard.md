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

> 本任务是迄今最重的：新增「事件 / 主题 / 标的池 / 产业链分组」四个概念层 + graph 渲染 + 相关性计算 + **LLM 智能匹配（必须实现）**。建议分阶段落地（见「落地节奏」）。
>
> **LLM 配置入口**：大模型连接信息（`LLM_API_BASE` / `LLM_API_KEY` / 模型名）在本看板页面内提供输入位置（一个「LLM 设置」面板，与事件输入区并列），不与 009 钥匙按钮（数据源专用）混用——LLM 能力是本任务专属，配置就近放在用它的地方。配置持久化到 `llm_config` 表，重启不丢。

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

#### 1.5 `llm_config` 表（大模型连接配置，单行）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TINYINT PK DEFAULT 1 | 恒为 1，单行配置 |
| api_base | VARCHAR(255) NULL | LLM API 地址（如 `https://api.openai.com/v1`） |
| api_key | VARCHAR(255) NULL | API Key（明文存储，见安全说明） |
| model | VARCHAR(64) NULL | 模型名（如 `gpt-4o-mini` / `deepseek-chat`） |
| enabled | TINYINT(1) NOT NULL DEFAULT 0 | 开关：是否启用 LLM 智能匹配 |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

> **单行约束**：启动时若表空，自动 INSERT `id=1` 默认行（全 NULL, enabled=0）。
> **持久化**：配置落库，重启服务/容器不丢；与 009 的 `data_source_config` 同构（单行配置表范式）。
> **安全说明**：当前无鉴权，api_key 明文存储（与 009 tushare_token 一致的处理）；GET 接口返回掩码（仅后 4 位）。后续可演进加密（见开放问题）。

新建 `backend/app/models/event.py`、`theme.py`、`llm_config.py`，在 `models/__init__.py` 注册。

### 2. SQL Migration

- **`mysql/init/08_event_dashboard.sql`**：五张表（含 `llm_config`）+ 预置 2~3 个内置主题（如「新茶饮产业链」「香料」「农业种植」）及其成分股（成分股一期可从概念板块拉取后写入，或留空由用户填充）+ `llm_config` 默认行（`id=1, enabled=0`）。
- **`mysql/migrations/009_event_dashboard.sql`**：同样五张表，已部署库用。

### 3. 数据拉取（概念板块成分股）

新建 `backend/app/services/fetcher/concept_fetcher.py`：

- `fetch_concept_stocks_em(concept_name) -> list[ConceptStock]`：调 `stock_board_concept_cons_em(symbol=概念名)`，返回成分股代码列表。
- 用于：预置主题时拉成分股、用户选概念板块补全标的池时实时拉取。
- 异常统一抛 `FetchError`。

> akshare 实测：`stock_board_concept_cons_em` 按概念名（如「新茶饮」「香精香料」）返回成分股。茉莉花无专属概念，需组合多个相关概念板块。

### 4. 智能匹配（必须实现，核心能力）

智能匹配是本看板的**核心卖点**——解决「朋友不知道有哪些相关股」的真问题。必须实现，**不降级**。

新建 `backend/app/services/matcher.py`：

- `smart_match(event_name, description) -> list[MatchedStock]`：
  1. **概念板块召回**（候选池）：用关键词扫 akshare 全部概念板块名（`stock_board_concept_em` 列表），召回相关概念及其成分股作为候选标的池。
  2. **LLM 判定**（必须）：把事件描述 + 候选标的列表喂给 LLM，让它判定：
     - 每只标的是否真相关（相关性高/中/低/无关）
     - 产业链角色（`upstream` / `midstream` / `downstream`）
     - 相关度权重（0~1）
     - 返回结构化 JSON。
  3. LLM 未配置（`enabled=0`）时，`smart_match` 返回错误 `ApiResponse.error("未配置 LLM，请在「LLM 设置」中填写连接信息并开启")`，**不退化为概念板块**（概念板块仅作为候选召回，不替代 LLM 判定）。

**LLM 调用实现**：
- OpenAI 兼容协议（`/v1/chat/completions`），兼容 OpenAI / DeepSeek / 通义千问等绝大多数国产模型。
- 请求：system prompt 说明任务（「你是 A 股产业链分析助手，根据事件判断相关股票的产业链角色」）+ user 内容（事件描述 + 候选标的代码/名称列表）+ `response_format: { type: "json_object" }` 要求结构化输出。
- 解析 LLM 返回 JSON → `MatchedStock` 列表；解析失败时记录原始返回、抛 `FetchError`。
- 超时 30s，失败重试 1 次。

**配置读取优先级**：
1. 数据库 `llm_config`（UI 设置，主入口，运行时可改）。
2. 环境变量 `LLM_API_BASE` / `LLM_API_KEY` / `LLM_MODEL`（`.env` / docker-compose，headless 部署兜底）。
3. 均无且 `enabled=0` → `smart_match` 拒绝执行返回错误。

**配置文件改动**：
- `backend/app/config.py` 新增：`llm_api_base: str = ""`、`llm_api_key: str = ""`、`llm_model: str = ""`（环境变量兜底）。
- `.env.example` 新增 `LLM_API_BASE=` / `LLM_API_KEY=` / `LLM_MODEL=`（注释：也可在事件看板「LLM 设置」面板填写）。
- `docker-compose.yml` 透传这三个环境变量。

> **隐私提示**：调用 LLM 会把事件描述发送给外部服务，UI 在「LLM 设置」面板与「智能匹配」按钮旁均需标注「事件描述将发送至配置的大模型服务」。

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
- `MatchedStock`：symbol、name、chain_role、weight、relevance（high/medium/low/none）
- `LlmConfigUpdate`：api_base、api_key、model、enabled
- `LlmConfigStatus`：enabled、api_base（可全显，非敏感）、api_key_masked（如 `••••abcd`）、model、configured（三项是否齐全）
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
| `/api/event/llm-config` | GET | 返回 `LlmConfigStatus`（api_key 掩码、enabled、configured） |
| `/api/event/llm-config` | PUT | 设置/更新 LLM 连接信息（api_base、api_key、model、enabled） |
| `/api/event/smart-match` | POST | 智能匹配：输入事件名/描述，LLM 判定相关标的与产业链角色 |
| `/api/event/concept-stocks` | GET | 参数 `concept`：实时拉概念板块成分股（补全候选池用） |
| `/api/event` | POST | 创建事件（含标的池，从主题复制或用户提交） |
| `/api/event/{id}` | GET | 事件详情 |
| `/api/event/{id}/stocks` | PUT | 更新事件标的池（增删/调链角色） |
| `/api/event/{id}/impact` | GET | 参数 `before, after`：返回 EventImpactData（三视图合并） |

**业务规则：**
- 所有接口返回统一 `ApiResponse`。
- **`smart-match` 是 LLM 强依赖**：`enabled=0` 或三项配置不齐时，直接返回 `ApiResponse.error("未配置 LLM，请在「LLM 设置」中填写连接信息并开启")`，**不降级**。概念板块仅作候选召回，不替代 LLM 判定。
- `llm-config` PUT：保存后不立即测试；可加可选 `test=true` 参数触发一次连通性测试（发一个极简 prompt 验证 key/base/model 有效）。
- `impact` 接口合并三视图数据一次返回（减少前端并发），内部调三个 compute 函数 + `ensure_price_data` 补数据。
- 创建事件时若传 `theme_id`，从 `theme_stock` 复制到 `event_stock`。

### 8. 路由注册

`backend/app/main.py`：

```python
from .api import ..., event_dashboard, ...
app.include_router(event_dashboard.router, prefix="/api/event", tags=["event"])
```

### 验收标准（后端）

- [x] 四张概念层表建成功（fresh 走 init/08，已部署走 migrations/009 + 启动自愈 create_all 兜底）
- [x] 内置主题预置成功（3 个内置主题 + 成分股样例，init/08 与启动自愈双路径）
- [x] `llm_config` 表建成功，默认行（id=1, enabled=0）就位
- [x] `stock_board_concept_cons_em` 拉概念板块成分股正常（候选召回；本机东财阻断时返回干净 FetchError，不阻断 LLM 判定）
- [x] **`smart-match` 在 LLM 配置齐全且 enabled=1 时，正确调用 LLM 返回结构化 MatchedStock（含 chain_role / weight / relevance）** — 实测 deepseek-v4-flash 稳定返回 3~5 只相关标的
- [x] **`smart-match` 在未配置 / enabled=0 / 三项不齐时，返回明确错误（不降级、不返回概念板块伪结果）** — 实测 disabled 时 code:1「未配置 LLM…」
- [x] LLM 返回非 JSON 或解析失败时，记录原始返回并抛 FetchError
- [x] `GET /llm-config` 返回 api_key 掩码、enabled、configured
- [x] `PUT /llm-config` 持久化配置，重启不丢（落库 llm_config 单行）
- [x] 事件窗口收益归一化正确（事件日=0 基准）
- [x] 相关性矩阵对称、对角线=1 — 实测 6×6 对角线全 1、对称
- [x] 创建事件从主题复制标的池成功；事件实例增删不影响主题模板
- [x] `impact` 接口合并三视图数据返回，字段完整
- [x] 行情缺失时 `ensure_price_data` 补拉
- [x] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. API 封装

`frontend/src/api/index.ts` 新增：

- `listThemes()`、`getTheme(id)`
- `getLlmConfig()`、`updateLlmConfig(body)`
- `smartMatch(body)`、`listConceptStocks(concept)`
- `createEvent(body)`、`getEvent(id)`、`updateEventStocks(id, body)`
- `getEventImpact(id, params)`
- 对应 TypeScript 类型 `Theme`、`EventStock`、`MatchedStock`、`LlmConfigStatus`、`EventImpactData`

### 2. 路由与导航

- `router/index.ts` 新增 `{ path: '/event', name: 'event', component: EventDashboardView }`
- `App.vue` `nav-links` 新增 `<RouterLink to="/event">事件看板</RouterLink>`，排在「估值看板」之后。

### 3. 页面（`frontend/src/views/EventDashboardView.vue`）

**布局：**

```
┌─────────────────────────────────────────────────────┐
│  事件冲击产业链看板                  [⚙ LLM 设置]   │  ← 标题 + LLM 设置入口
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

- **LLM 设置入口**（标题右侧 ⚙ 按钮）：点击弹出「LLM 设置」面板（Teleport 弹层），内容：
  - **API Base** 输入框（如 `https://api.openai.com/v1`，占位符提示常见值）
  - **API Key** 密码型输入框（占位符显示掩码 `••••abcd`）
  - **模型名** 输入框（如 `gpt-4o-mini` / `deepseek-chat`）
  - **启用开关**（toggle）：开启智能匹配；开启前校验三项非空，否则拦截提示
  - **「测试连接」按钮**（可选）：发极简 prompt 验证配置有效
  - 底部说明：「配置永久保存于本服务后端，重启后依然有效。⚠ 事件描述将发送至配置的大模型服务，请勿输入敏感信息。」
  - 状态回填：打开面板时调 `getLlmConfig()` 显示当前掩码与开关。
- **事件输入**：事件名 + 日期 + 描述（描述供智能匹配用）。
- **智能匹配按钮**：调 `/api/event/smart-match`。
  - **LLM 已启用**：返回候选标的列表（含 LLM 判定的 chain_role / weight / relevance），用户勾选确认。
  - **LLM 未启用/未配置**：按钮旁显示醒目提示「未配置 LLM，点击右上角 ⚙ 设置」，点击 ⚙ 跳到 LLM 设置面板。**不提供「概念板块兜底」伪结果**。
- **主题/概念补全**：选内置主题一键载入标的池；或选概念板块实时拉成分股补全（仅作候选池补充，不替代智能匹配）。
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

- [x] 导航新增「事件看板」入口
- [x] **「LLM 设置」面板**（⚙ 按钮）：可填 api_base/api_key/model + 启用开关，保存后掩码回显，重启后保持
- [x] **启用开关在三项未填齐时无法开启**（前端拦截 + 后端双重校验，实测 missing 字段 → code:1 拒绝）
- [x] **智能匹配在 LLM 启用时**：返回候选标的（含链角色/权重/相关度），可勾选入池
- [x] **智能匹配在 LLM 未启用时**：按钮旁醒目提示「未配置 LLM，点 ⚙ 设置」，不返回伪结果
- [x] 隐私提示（事件描述发送至外部）在设置面板与匹配按钮旁可见
- [x] 主题/概念补全标的池可用
- [x] 标的池表格可增删改链角色
- [x] 视图①：节点按上/中/下游分组，颜色映射涨跌，点击高亮
- [x] 视图②：多归一化曲线 + 事件日基准线 + 排行榜表格
- [x] 视图③：相关性热力图正确渲染，对角线=1
- [x] 窗口 N/M 调整三图联动
- [x] 明暗主题切换后样式正确
- [x] 复用 Ma120Chart 范式与 CSS 变量（vue-tsc + vite build 通过，690 模块）

---

## 数据复用与隔离策略

| 数据 | 来源 | 复用/隔离 |
|------|------|-----------|
| 个股行情 | `raw_price_daily`（已有） | `ensure_price_data` 补拉 |
| 概念板块成分股 | akshare `stock_board_concept_cons_em` | 实时拉取（候选召回），不入库或加缓存 |
| 事件/主题/标的池 | 四张概念层表 | 独立概念层，与行情隔离 |
| LLM 连接配置 | `llm_config` 表（单行） | 与 009 `data_source_config` 同构，独立 |
| 智能匹配 | akshare 概念召回 + **LLM 判定（必须）** | LLM 强依赖，配置不齐则拒绝 |

> 行情数据完全复用现有表；事件/主题/LLM 配置是新增的概念层，独立建表。

---

## 落地节奏（重要：本任务最重，建议分阶段）

本任务范围远大于其他图表，建议**分三阶段**，每阶段可独立上线：

**阶段一：智能匹配 + 波动对比看板（核心可用）**
- 后端：五张表（含 `llm_config`）+ LLM 设置 CRUD + `smart_match`（LLM 必须）+ 事件/主题/标的池 CRUD + `event_window_returns` + `window_cumulative_change`。
- 前端：LLM 设置面板 + 事件输入 + 智能匹配 + 标的池管理 + 视图②。
- 价值：立刻能回答「受灾后相关股涨跌多少」+ 用 LLM 自动发现相关股。**智能匹配随阶段一上线**（核心卖点不延后）。

**阶段二：产业链关系图 + 相关性热力图**
- 后端：`correlation_matrix` + `chain_groups`。
- 前端：视图①（ECharts graph）+ 视图③（heatmap）+ 三图联动。
- 价值：体验炸裂，补齐关系维度。

> 注：因智能匹配改为必须，原「阶段三」并入阶段一。落地节奏从三阶段收敛为两阶段。

---

## 开放问题（后续迭代）

- [ ] **graph 库评估**：一期 ECharts `graph`；若产业链层级多/布局复杂，二期评估 AntV G6。
- [ ] **概念板块缓存**：`stock_board_concept_cons_em` 实时拉取有限频，可加进程缓存。
- [ ] **LLM 配置加密**：当前 api_key 明文存储（与 009 tushare_token 一致）；后续引入对称加密或鉴权后按用户隔离。
- [ ] **LLM 提示词调优**：一期基础 prompt；后续根据实际匹配质量迭代 system prompt，支持 few-shot 示例。
- [ ] **多 LLM 提供商适配**：一期 OpenAI 兼容协议；后续若有非兼容提供商（如某些国产特殊接口）加适配层。
- [ ] **传导强度量化**：一期连线静态；二期用 Granger 因果或领先滞后相关量化传导方向与强度。
- [ ] **历史事件库**：预置经典事件（如过往自然灾害、政策事件）供回放研究。
- [ ] **产业链模板库**：扩充预置主题（新能源/半导体/消费等常见产业链），降低用户建池成本。
- [ ] **与估值/回测联动**：选中标的可一键跳转估值看板/回测，形成「事件发现标的 → 深度分析」链路。
