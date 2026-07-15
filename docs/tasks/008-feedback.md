# 008 — 问题反馈功能

## 目标

在导航栏主题切换按钮左侧新增「问题反馈」入口，支持访客提交意见（Markdown 语法），反馈有效期 3 天自动消失，最多保留最新 5 条，支持手工删除。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)

## Part A：后端

### 1. 数据模型

新建 `app/models/feedback.py`：

```
feedback 表：
- id          INT AUTO_INCREMENT PK
- content     TEXT NOT NULL          — 反馈内容（Markdown）
- nickname    VARCHAR(64) NULL        — 可选昵称
- created_at  DATETIME NOT NULL       — 创建时间（UTC）
- expires_at  DATETIME NOT NULL       — 过期时间（created_at + 3天）
- is_deleted  TINYINT(1) DEFAULT 0    — 软删除
```

在 `app/models/__init__.py` 中注册。

### 2. SQL Migration

新建 `mysql/init/02_feedback.sql`，包含建表语句（IF NOT EXISTS）。

### 3. Schema

新建 `app/schemas/feedback.py`：

- `FeedbackCreate`：content（必填，1~2000 字）、nickname（可选，≤64 字）
- `FeedbackItem`：id、content、nickname、created_at、expires_at
- `FeedbackCreated`：id

### 4. API 路由

新建 `app/api/feedback.py`，路由前缀 `/api/feedback`：

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/feedback` | POST | 提交反馈，自动设 expires_at = now + 3 天 |
| `/api/feedback` | GET | 获取有效反馈列表（未删除 + 未过期），按创建时间倒序 |
| `/api/feedback/{id}` | DELETE | 软删除指定反馈 |

**业务规则：**
- 提交时自动清理过期记录（is_deleted = 1）
- 提交后若有效反馈超过 5 条，软删除最早的
- 查询只返回 `is_deleted = 0 AND expires_at > now()` 的记录
- 返回统一 ApiResponse 格式

### 5. 路由注册

在 `main.py` 中 import feedback router 并注册：

```python
app.include_router(feedback.router, prefix="/api/feedback", tags=["feedback"])
```

### 验收标准（后端）

- [ ] feedback 表建成功（可手动执行 02_feedback.sql）
- [ ] POST 提交反馈返回 id
- [ ] GET 返回有效反馈列表，过期/删除的不出现
- [ ] DELETE 软删除成功，列表中不再出现
- [ ] 超过 5 条时自动清理最早的
- [ ] Swagger UI 可测试所有接口

---

## Part B：前端

### 1. API 封装

在 `frontend/src/api/index.ts` 新增：

- `listFeedback()` → GET /api/feedback
- `submitFeedback(body)` → POST /api/feedback
- `deleteFeedback(id)` → DELETE /api/feedback/{id}
- 对应 TypeScript 类型 `FeedbackItem`

### 2. 反馈组件

新建 `frontend/src/components/FeedbackWidget.vue`：

- 导航栏中显示反馈图标按钮（位于主题切换按钮左侧），使用以下 SVG：

```html
<svg class="feedback-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg">
  <path d="M813.7 386.7v-214c0-41.4-33.5-74.9-74.9-74.9H289.2c-41.4 0-74.9 33.6-74.9 74.9v214L514 599.8l299.7-213.1zM329.6 190h368.9c12.7 0 23.1 10.3 23.1 23.1 0 12.7-10.3 23.1-23.1 23.1H329.6c-12.7 0-23.1-10.3-23.1-23.1s10.3-23.1 23.1-23.1z m-23.1 115.3c0-12.7 10.3-23.1 23.1-23.1h230.6c12.7 0 23.1 10.3 23.1 23.1 0 12.7-10.3 23.1-23.1 23.1H329.6c-12.8 0-23.1-10.4-23.1-23.1z m615 61.4L553.8 628.1l367.7 261.4c4.7-9.3 7.6-19.7 7.6-30.8V397.5c-0.1-11.1-3-21.5-7.6-30.8zM99 397.5v461.1c0 38.2 31 69.2 69.2 69.2h691.7c9.9 0 19.2-2.1 27.7-5.9l-781-555.3c-4.7 9.4-7.6 19.8-7.6 30.9z" fill="currentColor"/>
</svg>
```

- SVG 尺寸约 20×20px，颜色用 `currentColor`（自适应明暗主题），hover 时颜色加深
- 点击后弹出面板（Teleport to body，遮罩层 + 居中卡片）
- 面板内容：
  - **提交表单**：textarea（反馈内容，支持 Markdown）+ 昵称输入框（可选）+ 提交按钮
  - **反馈列表**：按时间倒序展示，每条显示昵称/匿名、时间、内容（Markdown 渲染）、删除按钮
  - 底部提示：「反馈保留 3 天，最多显示最新 5 条」

**Markdown 渲染**（简易实现，无需引入库）：
- 支持：`**粗体**`、`*斜体*`、`` `代码` ``、`[链接](url)`、代码块、换行
- 先 HTML 转义，再逐条替换，防 XSS

### 3. 导航栏集成

在 `App.vue` 中：
- import FeedbackWidget 组件
- 放置在 `<nav class="nav-links">` 之后、`<button class="theme-switch">` 之前

### 4. 样式要求

- 弹窗面板使用项目现有 CSS 变量（`--surface`、`--border`、`--text` 等），自动适配明暗主题
- 面板宽度 540px，最大高度 80vh，内容区可滚动
- 删除按钮低透明度，hover 时显现

### 验收标准（前端）

- [ ] 导航栏`反馈图标按钮`按钮出现在主题切换左侧
- [ ] 点击弹出反馈面板，可输入内容并提交
- [ ] 提交后列表实时刷新
- [ ] 删除按钮可删除反馈
- [ ] Markdown 内容正确渲染（粗体、代码等）
- [ ] 明暗主题切换后面板样式正确
- [ ] 遮罩层点击关闭面板
