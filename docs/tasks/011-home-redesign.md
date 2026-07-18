# 011 — 首页改版

## 目标

重新设计首页与导航栏，让首页从「单薄的占位页」升级为**工具箱门户**：指路（去哪个工具）、续作（回到最近工作）、给上下文（市场当下怎么样）。

**导航栏：**
- 去掉 `nav-links` 里单独的「首页」链接。
- **左上角品牌区（logo + PortLab 文字）整体可点击**，点击回到首页；视觉上给予 hover 反馈。
- 品牌 logo 尺寸 22px → **24px**，与文字间距微调（8px → 10px）。

**首页内容块：**
1. **Hero**：PortLab + 定位语 + 后端状态（弱化为小绿点）。
2. **功能入口卡片**：定投回测 / MA120 策略，点击直达。
3. **市场概览/指数行情**：预置指数的最新价 + 涨跌幅 + 迷你 sparkline；**手动刷新按钮**补拉当天行情。
4. **最近回测记录** + **最近更新**：左右两栏，前者合并 DCA/MA120 最近 5 条，后者取 release note 前 3 条。
5. **Roadmap**：归纳展示**未实现**的任务（来自 `docs/tasks/` 目录 + `TASKS.md` 索引中状态为 ☐ 的项），分点列出，让用户了解产品下一步规划。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)
- [003 — 定投回测：计算引擎、API 与前端](./003-dca-compute-engine.md)
- [007 — 红利 MA120 策略回测](./007-ma120-strategy-backtest.md)
- [010 — 更新日志（Release Notes）功能](./010-release-notes.md)（「最近更新」块数据来源；未上线前该块做空状态占位）

> 与 009（数据源）无依赖：首页市场概览读取 `raw_price_daily`，不区分 AkShare/Tushare 源。

---

## Part A：后端

### 1. 最近回测记录接口

新建 `app/schemas/recent.py` 与 `app/api/recent.py`（或并入 `api/backtest.py`）。

#### 1.1 接口

```
GET /api/backtest/recent?limit=5
```

返回最近 `limit` 条回测记录，合并 DCA（`result_dca_summary`）与 MA120（`result_ma120_summary`）两表，按时间倒序。

#### 1.2 返回结构

```json
{
  "code": 0,
  "data": [
    {
      "task_id": "ma120_510880_..._batch",
      "type": "ma120",
      "symbol": "510880",
      "symbol_name": "红利ETF",
      "return_rate": 12.35,
      "period_text": "2023-01-01 ~ 2026-07-15",
      "created_text": "2026-07-16"
    }
  ]
}
```

- `type`：`'dca'` / `'ma120'`，用于前端类型标签与跳转路由。
- `return_rate`：直接取两表共有的 `total_return_rate` 字段。
- `symbol_name`：复用 `symbol_catalog.lookup_name(symbol)`。
- `period_text`：从 task_id 解析的起止日期，或从表内 `start_date` / `end_date` 字段格式化（两表都有这两列）。

#### 1.3 「最近」的排序基准（关键设计点）

两张 summary 表**均无 `created_at` 字段**，task_id 为 PK 且其中编码了起止日期与参数。排序方案：

- **推荐：从 task_id 解析日期**。两表的 task_id 规则都含 `_{start}_{end}_` 段（如 `ma120_510880_20230101_20260715_...`），`end` 段（`YYYYMMDD`）作为「记录时间近似值」用于排序。
- 实现：各表 `SELECT task_id, symbol, total_return_rate, start_date, end_date`，在应用层解析 end 段或直接用 `end_date` 列倒序，合并后取前 `limit` 条。
- **权衡**：用 `end_date` 排序意味着「回测结束日期越近越靠前」，并非真正的「创建时间」。对多数场景够用（用户通常关心近期区间的回测）；若后续需要精确创建时间，需给两张表加 `created_at` 列（列入「开放问题」）。

> 一期采用 `end_date DESC` 作为排序基准，文档与接口注释需注明此语义。

### 2. 市场概览接口

新建 `app/schemas/market.py` 与 `app/api/market.py`。

#### 2.1 接口

```
GET /api/market/overview
```

返回预置指数列表的概览数据，**仅从 `raw_price_daily` 读取已入库数据**，不主动发起拉取。

#### 2.2 预置指数

| 代码 | 名称 | 说明 |
|------|------|------|
| 510300 | 沪深300ETF | 大盘基准 |
| 510880 | 红利ETF | MA120 策略主标的 |
| 159915 | 创业板ETF | 成长风格 |
| 510050 | 上证50ETF | 超大盘 |

> 列表可配置，一期硬编码于后端常量（如 `app/services/market.py` 的 `OVERVIEW_SYMBOLS`）。

#### 2.3 返回结构

```json
{
  "code": 0,
  "data": {
    "as_of": "2026-07-15",
    "items": [
      {
        "symbol": "510300",
        "name": "沪深300ETF",
        "latest_date": "2026-07-15",
        "latest_close": 3.952,
        "prev_close": 3.948,
        "change_pct": 0.10,
        "sparkline": [3.91, 3.92, 3.90, ..., 3.952]
      }
    ],
    "missing": ["159915"]
  }
}
```

- `latest_date` / `latest_close`：该 symbol 在 `raw_price_daily` 中**最新一条**的日期与收盘。
- `prev_close`：前一条收盘（用于算当日涨跌）。
- `change_pct`：`(latest_close - prev_close) / prev_close × 100`。
- `sparkline`：最近 30 个交易日收盘价数组（迷你折线用）。
- `as_of`：所有 items 中最新的 `latest_date`（首页显示「数据截至 YYYY-MM-DD」）。
- `missing`：库里完全没数据的 symbol 列表（前端做空状态提示「该指数暂无行情，点刷新拉取」）。

#### 2.4 手动刷新（复用现有接口）

首页「刷新行情」按钮对每个（或全部）预置指数调用现有 `POST /api/data/fetch`，body 含 `symbol` 与一个覆盖到今天的日期区间：

```json
{ "symbol": "510300", "start_date": "2026-07-01", "end_date": "2026-07-17" }
```

- 拉取完成后重新调 `/api/market/overview` 刷新展示。
- **不新建刷新接口**，直接复用 002 的 `/api/data/fetch`（已带 UPSERT 幂等、避免重复拉取）。
- 刷新按钮逐个调用或并发调用均可；并发时注意数据源限频（AkShare/Tushare），一期建议**串行**调用避免触发限频。

### 3. Roadmap 接口

新建 `app/schemas/roadmap.py` 与 `app/api/roadmap.py`。

#### 3.1 设计原则：TASKS.md 为真相源，目录为校验

状态判定以根目录 `TASKS.md` 表格的「状态」列为准（☑ 已完成 / ☐ 未实现），并与 `docs/tasks/` 目录交叉校验：

- **TASKS.md 列了且状态 ☐** → 进入 roadmap（核心来源）。
- **文档存在但 TASKS.md 未列入** → 索引漏录，记录告警（日志 `WARNING`），**不进 roadmap**（避免展示无序号或状态不明的项）。
- **TASKS.md 列了但文档不存在** → 死链，跳过并日志告警。

> 理由：纯扫目录无法判定状态（已完成的 007/008 文档仍在），必须以 `TASKS.md` 的 ☑/☐ 为准；目录扫描用于发现索引遗漏，保证两者一致。**这要求维护纪律**：新增 task 文档后须同步登记到 `TASKS.md`（已在本任务修正 009-011 的登记）。

#### 3.2 接口

```
GET /api/roadmap
```

返回未实现任务（☐）的归纳列表，按编号升序。

#### 3.3 返回结构

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "009",
        "title": "Tushare 数据源扩展",
        "summary": "支持 Tushare 作为可选数据源，开关启用，数据独立成表",
        "doc_url": "/docs/tasks/009-tushare-data-source.md",
        "category": "数据"
      },
      {
        "id": "010",
        "title": "更新日志（Release Notes）功能",
        "summary": "导航栏铃铛图标，展示最新 5 条变更记录",
        "doc_url": "/docs/tasks/010-release-notes.md",
        "category": "产品"
      },
      {
        "id": "011",
        "title": "首页改版",
        "summary": "首页重设计 + 导航品牌区可点击回首页",
        "doc_url": "/docs/tasks/011-home-redesign.md",
        "category": "前端"
      }
    ],
    "total": 3
  }
}
```

- `id` / `title`：从 `TASKS.md` 表格解析（编号 + 任务名，剥离 `[...](...)` 链接语法）。
- `summary`：一句话归纳。来源优先级：
  1. `TASKS.md` 表格若增加可选「摘要」列则直接用（**一期建议加此列**，最省事）；
  2. 否则读对应 task 文档的「## 目标」段首句自动提取（正则取第一句，兜底）。
- `doc_url`：相对路径，前端拼成可点击链接（或仅作 hover 提示）。
- `category`：可选分类标签（数据 / 产品 / 前端 / 后端 / 策略），便于分组展示。一期可省略或全部归为「规划中」。

#### 3.4 TASKS.md 建议：新增「摘要」列

为让 roadmap 展示有质量的一句话归纳（而非生硬的文档标题），建议把 `TASKS.md` 表格扩为四列：

```markdown
| # | 任务 | 摘要 | 状态 |
|---|------|------|------|
| 009 | [Tushare 数据源扩展](...) | 支持 Tushare 可选数据源，开关启用，数据独立成表 | ☐ |
```

`summary` 字段直接读此列，避免后端解析每个文档的「目标」段（解析兜底逻辑仍保留，作为该列缺失时的 fallback）。本任务实施时一并改造 `TASKS.md`。

#### 3.5 解析实现要点

- 读 `TASKS.md`：逐行匹配 `^\| (\d{3}) \| \[(.+?)\]\((.+?)\) \| (☑|☐) \|`（兼容未来加摘要列时多一列）。
- 缓存：`TASKS.md` 变动频率低，可加进程内缓存（如 5 分钟 TTL），避免每次请求都读盘解析。
- 文档目录扫描：`os.listdir('docs/tasks')` 拿现有文档编号集合，与 TASKS.md 列表做差集告警。

### 4. 路由注册

`backend/app/main.py`：

```python
from .api import backtest, data, feedback, health, ma120, market, recent, release_note, roadmap, symbols
...
app.include_router(recent.router, prefix="/api/backtest", tags=["backtest"])   # /api/backtest/recent
app.include_router(market.router, prefix="/api/market", tags=["market"])       # /api/market/overview
app.include_router(roadmap.router, prefix="/api/roadmap", tags=["roadmap"])    # /api/roadmap
```

### 验收标准（后端）

- [ ] `GET /api/backtest/recent?limit=5` 返回合并 DCA+MA120 的最近记录，按 `end_date` 倒序
- [ ] 每条含 `task_id`、`type`、`symbol`、`symbol_name`、`return_rate`、`period_text`
- [ ] 两表均无数据时返回空数组（非报错）
- [ ] `GET /api/market/overview` 返回预置指数的最新价、涨跌幅、sparkline、`as_of`
- [ ] 库里无数据的指数进入 `missing` 数组，不报错
- [ ] 刷新流程：调用 `POST /api/data/fetch` 后再次 `/api/market/overview` 能看到最新数据
- [ ] **`GET /api/roadmap` 返回 TASKS.md 中状态 ☐ 的任务，按编号升序**
- [ ] roadmap 每条含 `id`、`title`、`summary`、`doc_url`、（可选）`category`
- [ ] **TASKS.md 列了但文档不存在**时跳过并日志告警；**文档存在但 TASKS.md 未列**时日志告警
- [ ] 进程内缓存生效（重复请求不重复解析 TASKS.md）
- [ ] 返回统一 `ApiResponse`，Swagger UI 可测试

---

## Part B：前端

### 1. 导航栏改造（`App.vue`）

- 模板：将 `<div class="brand">` 改为 `<RouterLink to="/" class="brand">`，内含 logo SVG 与「PortLab」文字。
- 模板：`nav-links` 删除 `<RouterLink to="/">首页</RouterLink>`，仅留功能页。
- 样式 `.brand`：
  - 新增 `cursor: pointer`、`text-decoration: none`、`color: var(--text)`（覆盖 `<a>` 默认样式）。
  - hover 反馈：logo 与文字色微变（如 `color: var(--primary)`）或底色 `var(--hover-bg)`，加 `transition`。
  - **主页态不加 active 下划线**（通过 `:not(.router-link-active)` 或不设 `.router-link-active` 样式实现，区别于功能页的下划线 active 态）。
- 样式 `.brand-logo`：
  ```css
  .brand-logo {
    width: 24px;       /* 22 → 24 */
    height: 24px;
    margin-right: 10px; /* 8 → 10 */
    flex-shrink: 0;
  }
  ```

### 2. API 封装（`frontend/src/api/index.ts`）

新增：

- `listRecentBacktests(limit=5)` → GET `/api/backtest/recent?limit=`
- `getMarketOverview()` → GET `/api/market/overview`
- `fetchMarketData(symbol, start, end)` → POST `/api/data/fetch`（刷新按钮用，复用现有 `fetchPrices`）
- `getRoadmap()` → GET `/api/roadmap`
- 类型 `RecentBacktestItem`、`MarketOverview`、`MarketItem`、`RoadmapItem`、`Roadmap`

### 3. 首页重写（`Home.vue`）

#### 3.1 布局草图

```
┌──────────────────────────────────────────────────┐
│  PortLab · 个人投资分析工具箱      • 后端正常    │  ← Hero（定位语 + 状态小绿点）
├──────────────────────────────────────────────────┤
│  ┌─ 定投回测 ──────┐  ┌─ MA120 策略 ─────┐       │  ← 功能入口卡片
│  │  📈 简述…        │  │  📊 简述…         │       │
│  │           进入 →│  │           进入 → │       │
│  └─────────────────┘  └──────────────────┘       │
├──────────────────────────────────────────────────┤
│  市场概览    数据截至 2026-07-15  [🔄 刷新行情]   │  ← 市场概览
│  ┌─沪深300─┐ ┌─红利ETF─┐ ┌─创业板─┐ ┌─上证50─┐   │
│  │3.952    │ │2.85     │ │…       │ │…       │   │
│  │+0.10% 🟢│ │-0.35% 🔴│ │        │ │        │   │
│  │ ╱╲╱╲╱   │ │ ╲╱╲╱╲   │ │ spark  │ │ spark  │   │
│  └─────────┘ └─────────┘ └────────┘ └────────┘   │
├──────────────────────────────────────────────────┤
│  最近回测记录                                    │  ← 独立板块（通栏）
│  ─ DCA    510300  +12.3%   2026-07-16           │
│  ─ MA120  510880  +8.2%    2026-07-15           │
│  ─ DCA    159915  -2.1%    2026-07-12           │
│  ─ …                                            │
├──────────────────────────────────────────────────┤
│  最近更新                 │  Roadmap · 规划中    │  ← 左右两栏
│  • feature  MA120… 7/16   │  009 Tushare 数据源  │
│  • bugfix    图表…  7/16  │     开关启用，独立成表│
│  • improvement …    7/15  │  010 更新日志         │
│  查看全部 → (衔接 010 弹层) │     铃铛图标，最新5条│
│                           │  011 首页改版         │
│                           │     品牌区可点击回首页│
└──────────────────────────────────────────────────┘
```

#### 3.2 功能入口卡片

- 纯前端，2 张卡片：定投回测（`/backtest`）、MA120 策略（`/ma120`）。
- 每张含图标、策略名、一句话简述、「进入 →」。
- 卡片整体可点（`<RouterLink>`），hover 抬升阴影。
- 预留扩展位：后续新策略（如任务 006 智能定投独立页）可加第三张。

#### 3.3 市场概览

- 卡片网格，每个指数一张小卡：名称、最新价、涨跌幅（红涨绿跌或按 A 股习惯绿涨红跌，与项目其他图表配色一致）、sparkline 迷你折线（纯 SVG 或轻量 ECharts `graphic`）。
- 顶部右侧：「数据截至 {as_of}」+「🔄 刷新行情」按钮。
- 刷新按钮：loading 态禁用；串行调 `fetchMarketData` 拉每个指数当天区间（如最近 30 天），完成后重载 overview。
- `missing` 中的指数显示「暂无行情」占位，不阻塞其他卡片。

#### 3.4 最近回测记录

- 列表，每行：类型标签（DCA/MA120，复用 010 的彩色 chip 思路）、标的名称、收益率（红绿）、日期。
- 点击行：带 `task_id` 跳转到对应回测页（`/backtest?task=xxx` 或 `/ma120?task=xxx`）。
  > 注：回测页需支持 `?task=` query 预载已有结果（当前可能未实现，见「开放问题」）。
- 空状态：「还没有回测记录，去试试吧 →」带跳转链接。

#### 3.5 最近更新（release note 预览）

- 调 `listReleaseNotes()` 取前 3 条，简洁列表：类型标签 + 日期 + 标题。
- 「查看全部 →」触发任务 010 的更新日志弹层（`ReleaseNotesWidget` 的打开方法，可通过事件或共享状态触发）。
- 010 未上线时该块显示空状态占位。

#### 3.6 Roadmap（规划中）

- 调 `getRoadmap()` 拉取未实现任务列表，按编号升序分点展示。
- 每条结构：**编号 + 标题**（粗体）+ **一句话摘要**（弱化色）。可选 `category` 标签用于分组（如「数据 / 产品 / 前端」分栏）。
- hover 时显示「查看任务文档」提示，点击可跳转 `doc_url`（相对路径，前端拼成 `/docs/tasks/xxx.md`；若 SPA 不托管 md 文件，则改为 hover tooltip 或隐藏链接，仅展示文字）。
- **分点归纳**：纵向列表（非卡片网格），每条带左侧编号徽章，整体偏「待办清单」观感。
- **空状态**：无未实现任务时显示「暂无规划，敬请期待 🎉」（理想态，说明产品成熟）。
- 数量较多（>5）时整块可滚动或折叠，避免抢占首屏。

#### 3.7 Hero 区

- PortLab 标题 + 定位语「个人投资分析工具箱 · 定投 / MA120 策略回测」。
- 后端状态**弱化**：不再是独立卡片，改为标题旁的小绿点（或灰点表示异常）+ tooltip「后端正常 / 连接失败」。

### 4. 样式要求

- 复用项目现有 CSS 变量（`--surface`、`--border`、`--text`、`--text-secondary`、`--primary`、`--hover-bg`、`--shadow` 等），自动适配明暗主题。
- 卡片圆角、阴影、hover 抬升与现有回测页风格统一。
- 涨跌色与项目其他图表一致（确认 A 股习惯：红涨绿跌，或沿用现有 ECharts 配色）。
- 响应式：窄屏卡片网格自动降列（4→2→1）。

### 验收标准（前端）

- [ ] 品牌区（logo + PortLab）可点击回首页，hover 有反馈
- [ ] 导航 `nav-links` 不再有「首页」项
- [ ] logo 尺寸为 24px，视觉协调
- [ ] 主页时品牌区无 active 下划线
- [ ] 功能入口卡片点击直达对应回测页
- [ ] 市场概览显示指数最新价/涨跌幅/sparkline，标注「数据截至」
- [ ] 刷新按钮可补拉当天行情并更新展示，loading 态正常
- [ ] 最近回测记录显示最近 5 条，点击跳转
- [ ] 最近更新显示前 3 条 release note（010 上线后）
- [ ] **Roadmap 分点展示未实现任务（编号 + 标题 + 摘要）**
- [ ] Roadmap 数据与 `TASKS.md` 的 ☐ 项一致，不含已完成的 007/008
- [ ] Roadmap 空状态显示「暂无规划」
- [ ] 各模块空状态、加载、错误重试齐全
- [ ] 明暗主题切换后首页样式正确

---

## 落地节奏建议

为降低单次改动风险，分两步实施：

**第一步（导航 + 卡片 + 最近记录 + release 预览 + roadmap）**
- 改 `App.vue` 导航、logo 尺寸。
- 重写 `Home.vue` 的 Hero + 功能入口卡片 + 最近回测记录 + 最近更新 + Roadmap。
- 后端新增 `/api/backtest/recent` 与 `/api/roadmap`（后者仅读 TASKS.md，零数据层依赖）。
- 不依赖市场数据，可独立上线见效。

**第二步（市场概览）**
- 新增 `/api/market/overview`。
- Home.vue 增加市场概览区块 + 刷新按钮。
- 含实时性策略（手动刷新）的完整实现与联调。

---

## 开放问题（后续迭代）

- [ ] **回测页 `?task=` 预载**：当前回测页可能不支持从 URL query 直接载入已有 task 结果，需确认/改造，否则「最近记录点击跳转」无法直达结果。
- [ ] **summary 表 `created_at` 列**：为精确「创建时间」排序，可给 `result_dca_summary` / `result_ma120_summary` 加 `created_at`（迁移），替代用 `end_date` 近似。
- [ ] **市场概览实时性**：一期手动刷新；后续可加「每日首次访问自动补拉一次」或后端定时任务。
- [ ] **首页个性化**：用户收藏的标的置顶、常用策略快捷入口（需引入用户体系，当前无鉴权）。
- [ ] **sparkline 渲染**：纯 SVG vs ECharts mini 图，按性能与一致性择一。
- [ ] **指数列表可配置**：一期硬编码，后续可由配置或管理后台维护。
- [ ] **Roadmap 进度展示**：当前仅区分「已完成 / 未实现」两态；后续可加「进行中」态（需 TASKS.md 支持 `◐` 半完成标记），并展示总体进度百分比（如 8/11 完成）。
- [ ] **Roadmap 分类与排序**：一期按编号升序；后续可按 `category` 分栏、按优先级排序，或允许 TASKS.md 自定义排序权重。
