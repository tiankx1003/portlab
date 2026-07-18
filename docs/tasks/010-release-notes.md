# 010 — 更新日志（Release Notes）功能

## 目标

在导航栏右上角新增「更新日志」入口（喇叭/公告图标按钮），点击弹出面板，**滚动展示**最新的变更记录（Bug 修复 / 新功能 / 优化），每条带**日期**，仅显示**最新 5 条**。

- 更新日志由**后端维护**（运营 / 开发手动添加），前端只读展示，便于用户感知产品迭代。
- 数据源可选：一期从数据库 `release_notes` 表读取；后续可改为从 CHANGELOG / Git tag 自动生成（见「开放问题」）。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)

> 与 008（问题反馈）形态相似（右上角图标 + 弹层），但方向相反：反馈是用户写、产品看；更新日志是产品写、用户看。可与 009（数据源）的钥匙图标并列共存于 `.nav-actions`。

---

## Part A：后端

### 1. 数据模型

新建 `app/models/release_note.py`：

```
release_notes 表：
- id           INT AUTO_INCREMENT PK
- title        VARCHAR(128) NOT NULL     — 标题（一句话摘要，如「MA120 新增止盈步长参数」）
- type         VARCHAR(16)  NOT NULL     — 类型：feature / bugfix / improvement / notice
- detail       TEXT NULL                  — 详情（可选，Markdown，多条要点）
- released_at  DATE NOT NULL              — 发布日期（业务日期，非创建时间）
- is_deleted   TINYINT(1) DEFAULT 0       — 软删除（误录可隐藏）
- created_at   DATETIME NOT NULL          — 记录创建时间（UTC）
```

在 `app/models/__init__.py` 中注册导出 `ReleaseNote`。

### 2. SQL Migration

遵循现有 `init/`（fresh）+ `migrations/`（已部署）双写：

- **新建 `mysql/init/04_release_notes.sql`**：`USE portlab;` + `CREATE TABLE IF NOT EXISTS release_notes (...)`。
- **新建 `mysql/migrations/005_release_notes.sql`**：同样建表语句，供已部署库手动执行。文件头按现有惯例写明「一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/04_release_notes.sql 包含」。

### 3. 预置种子数据

为让首版上线即有内容，`init/04_release_notes.sql` 在建表后用 `INSERT ... ON DUPLICATE KEY UPDATE` 预置最新 5 条（对应当前真实迭代），示例（released_at 与标题对齐近期 commit）：

```sql
INSERT INTO release_notes (title, type, detail, released_at) VALUES
('MA120 新增止盈步长参数',    'feature',     'batch 卖出方式下可配置止盈步长，灵活控制分批卖出节奏', '2026-07-16'),
('问题反馈功能上线',          'feature',     '右上角反馈图标，支持 Markdown 提交，反馈保留 3 天',     '2026-07-16'),
('图表图例提示与卡片交互优化', 'improvement', '图例新增提示图标；MA120 卡片/表单交互打磨',           '2026-07-16'),
('红利 MA120 策略回测全链路', 'feature',     '新增 MA120 策略回测（计算引擎 + API + 前端）',        '2026-07-15'),
('自定义品牌图标',            'improvement', 'favicon 与左上角 Logo 自定义',                       '2026-07-12')
ON DUPLICATE KEY UPDATE title=VALUES(title);
```

> 上述仅作种子示例，实施时按当时实际迭代为准调整。`migrations/005_release_notes.sql` 中**不预置**这些数据（已部署库由运营自行维护），仅建表。

### 4. Schema

新建 `app/schemas/release_note.py`：

- `ReleaseNoteItem`：id、title、type、detail、released_at
  - `type` 枚举值：`feature`（新功能）/ `bugfix`（修复）/ `improvement`（优化）/ `notice`（公告）
- 前端展示用，不含内部字段（is_deleted / created_at）

### 5. API 路由

新建 `app/api/release_note.py`，路由前缀 `/api/release-notes`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/release-notes` | GET | 返回最新 5 条（未删除），按 `released_at` 倒序 |

**业务规则：**
- 查询 `is_deleted = 0` 的记录，按 `released_at DESC, id DESC` 排序，**LIMIT 5**。
- `detail` 为 Markdown 原文，由前端渲染（与 008 反馈面板 Markdown 渲染逻辑一致，可复用）。
- 返回统一 `ApiResponse` 格式。

> **一期只做只读 GET**。增删改接口（POST/PUT/DELETE）属于运营管理功能，一期不做（数据通过 SQL 直接维护），列入「开放问题」后续补管理后台或脚本。

### 6. 路由注册

`backend/app/main.py`：

```python
from .api import backtest, data, feedback, health, ma120, release_note, symbols
...
app.include_router(release_note.router, prefix="/api/release-notes", tags=["release-notes"])
```

### 验收标准（后端）

- [ ] `release_notes` 表建成功（fresh 走 init/04，已部署走 migrations/005）
- [ ] fresh 安装后表内预置 5 条种子数据
- [ ] GET `/api/release-notes` 返回最新 5 条，按日期倒序
- [ ] 软删除（`is_deleted=1`）的记录不返回
- [ ] 返回统一 `ApiResponse` 格式，Swagger UI 可测试

---

## Part B：前端

### 1. API 封装

在 `frontend/src/api/index.ts` 新增：

- `listReleaseNotes()` → GET `/api/release-notes`
- 对应 TypeScript 类型 `ReleaseNoteItem`（id、title、type、detail、released_at）、`type` 联合类型 `'feature'|'bugfix'|'improvement'|'notice'`

### 2. 更新日志组件

新建 `frontend/src/components/ReleaseNotesWidget.vue`：

- **图标按钮**：36×36px 无边框（class 复用 `.feedback-btn` 同款样式），20×20 铃铛 SVG（使用用户指定图标），颜色用 `currentColor`，hover 加深；有未读时可在图标右上角加小红点（开放项，一期可选）：

```html
<svg class="release-icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg">
  <path d="M889.92 749.728c-1.184-1.664-119.232-165.888-119.232-287.392 0-168.448-76.16-254.784-162.688-287.008L608 160c0-52.928-43.072-96-96-96s-96 43.072-96 96l0 15.296c-86.528 32.224-162.688 118.56-162.688 287.008 0 121.216-118.016 285.248-119.2 286.88-5.408 7.456-7.36 16.928-5.312 25.952 2.048 8.96 7.872 16.672 16 21.024 5.664 3.072 107.392 57.28 233.536 84.512C399.744 947.072 452.16 992 512 992s112.256-44.928 133.632-111.296c126.112-27.104 227.84-80.992 233.504-84.032 8.16-4.352 14.016-12.032 16.064-21.024S895.328 757.184 889.92 749.728zM480 160c0-17.632 14.368-32 32-32s32 14.368 32 32l0 0.928C536.832 160.32 529.728 160 522.688 160l-21.376 0C494.272 160 487.168 160.32 480 160.928L480 160zM512 928c-22.336 0-43.136-13.408-57.984-35.296C473.216 894.72 492.608 896 512 896s38.784-1.28 57.984-3.296C555.136 914.624 534.304 928 512 928z" fill="currentColor"/>
</svg>
```

- 点击后弹出面板（Teleport to body，遮罩层 + 居中卡片），内容：
  - **标题区**：「更新日志」+ 副标题「最近 5 条变更」
  - **滚动列表**：垂直排列 5 条，每条结构：
    - 顶部行：**类型标签**（彩色小 chip：feature=绿 / bugfix=红 / improvement=蓝 / notice=灰）+ **日期**（右侧，`YYYY-MM-DD`）
    - **标题**：粗体一句话摘要
    - **详情**：可选，Markdown 渲染（复用 008 反馈面板的简易 Markdown 渲染：粗体 / 斜体 / 代码 / 链接 / 换行，先 HTML 转义防 XSS）
  - **空状态**：无数据时显示「暂无更新记录」
  - 底部提示：「仅展示最近 5 条变更」
- **滚动显示**：列表区设固定最大高度（如 `max-height: 60vh; overflow-y: auto`），超出滚动；面板整体 `max-height: 80vh`。

**交互：**
- 打开面板时调用 `listReleaseNotes()` 拉取；可在组件挂载时预拉一次缓存，打开即时显示。
- 遮罩层点击关闭。
- 加载中显示骨架 / loading；失败显示错误信息与重试。

### 3. GitHub 仓库入口（外链图标按钮）

与更新日志并列，在导航栏增加一个 **GitHub 图标按钮**，点击在新标签页打开本项目仓库。

- **仓库地址**：`https://github.com/tiankx1003/portlab`
- **图标按钮**：36×36px 无边框（与 `.feedback-btn` / 更新日志按钮同款样式），20×20 GitHub SVG（使用用户指定图标），`fill` 改为 `currentColor` 自适应明暗主题：

```html
<a class="nav-icon-btn github-link"
   href="https://github.com/tiankx1003/portlab"
   target="_blank"
   rel="noopener noreferrer"
   title="GitHub 仓库"
   aria-label="GitHub 仓库">
  <svg class="github-icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg">
    <path d="M511.6 76.3C264.3 76.2 64 276.4 64 523.5 64 718.9 189.3 885 363.8 946c23.5 5.9 19.9-10.8 19.9-22.2v-77.5c-135.7 15.9-141.2-73.9-150.3-88.9C215 726 171.5 718 184.5 703c30.9-15.9 62.4 4 98.9 57.9 26.4 39.1 77.9 32.5 104 26 5.7-23.5 17.9-44.5 34.7-60.8-140.6-25.2-199.2-111-199.2-213 0-49.5 16.3-95 48.3-131.7-20.4-60.5 1.9-112.3 4.9-120 58.1-5.2 118.5 41.6 123.2 45.3 33-8.9 70.7-13.6 112.9-13.6 42.4 0 80.2 4.9 113.5 13.9 11.3-8.6 67.3-48.8 121.3-43.9 2.9 7.7 24.7 58.3 5.5 118 32.4 36.8 48.9 82.7 48.9 132.3 0 102.2-59 188.1-200 212.9 23.5 23.2 38.1 55.4 38.1 91v112.5c0.8 9 0 17.9 15 17.9 177.1-59.7 304.6-227 304.6-424.1 0-247.2-200.4-447.3-447.5-447.3z" fill="currentColor"/>
  </svg>
</a>
```

**实现要点：**
- 用原生 `<a target="_blank" rel="noopener noreferrer">`，无需组件状态，最简单；`rel="noopener noreferrer"` 防止新标签页通过 `window.opener` 访问当前页（安全最佳实践）。
- hover 反馈与反馈/更新日志按钮一致（底色 `--hover-bg`、图标色加深）。
- 仓库地址建议抽成前端常量（如 `frontend/src/config.ts` 的 `GITHUB_REPO`），便于后续统一维护 / 改为可配置。

> GitHub 链接是纯前端静态外链，**不涉及后端**，无 API、无数据表。

### 4. 导航栏集成

在 `App.vue` 中：

- `import ReleaseNotesWidget from './components/ReleaseNotesWidget.vue'`
- 放置在 `.nav-actions` 内。**顺序约定**（与 008/009 协调）：`反馈 → 数据源(钥匙) → 更新日志(铃铛) → GitHub → 主题切换`，即 GitHub 图标放在更新日志与主题切换之间（外链类靠右收尾）。

### 5. 样式要求

- 复用项目现有 CSS 变量（`--surface`、`--border`、`--text`、`--text-secondary`、`--primary`、`--hover-bg` 等），自动适配明暗主题。
- 面板宽度 ~480px（比反馈面板略宽，便于展示详情），最大高度 80vh，内容区可滚动。
- 类型标签用低饱和填色 + 深色文字，四种类型颜色区分清晰但不刺眼。
- 日期用 `--text-secondary` 弱化，突出标题。

### 验收标准（前端）

- [ ] 导航栏出现更新日志图标按钮，位于钥匙图标与 GitHub 图标之间
- [ ] 点击弹出更新日志面板，展示最新 5 条
- [ ] 每条显示类型标签 + 日期 + 标题 + 详情（可选）
- [ ] 列表超过面板高度时可滚动
- [ ] 类型标签四种颜色正确区分
- [ ] Markdown 详情正确渲染（粗体、代码、链接等）
- [ ] 空状态显示「暂无更新记录」
- [ ] 明暗主题切换后面板样式正确
- [ ] 遮罩层点击关闭面板
- [ ] **GitHub 图标按钮**出现在更新日志与主题切换之间
- [ ] 点击 GitHub 图标在新标签页打开 `https://github.com/tiankx1003/portlab`
- [ ] GitHub 图标 hover 反馈与其它图标按钮一致，明暗主题适配

---

## 开放问题（后续迭代）

- [ ] **管理后台 / 脚本**：提供 POST/PUT/DELETE 接口或 CLI 脚本，方便运营免 SQL 维护更新日志。
- [ ] **自动生成**：从 Git commit / CHANGELOG / Git tag 自动提取变更，减少手工录入。
- [ ] **未读小红点**：记录用户上次查看时间（localStorage），有新记录时图标角标提示。
- [ ] **分页 / 「查看全部」**：一期固定 5 条；后续可加分页或独立「全部更新日志」页面。
- [ ] **多语言**：title/detail 国际化（当前仅中文）。
