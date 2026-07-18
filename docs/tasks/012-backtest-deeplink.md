# 012 — 回测结果直达（URL `?task=` 预载）

## 目标

定投回测页（`/backtest`）与 MA120 策略页（`/ma120`）支持从 URL query `?task=<task_id>` 直接载入已算好的回测结果，使首页「最近回测记录」点击行能**直达结果**，而非跳到空表单。

## 背景 / 动机

011 首页「最近回测记录」点击会 `router.push({ path, query: { task } })`，但两个回测页当前不读取 `task` query，点击后只到空表单、需手动重填参数重跑。本任务补齐这一环，打通「最近记录 → 直达」闭环（011 开放问题）。

## 要点

- 两个回测页 `onMounted` 读取 `route.query.task`，非空则直接 `getChart(taskId)` + `getSummary(taskId)` 渲染。
- 同时从 summary 反推表单参数（symbol / 区间 / 模式 / 资金模式等）回填，便于在已有结果上微调重跑。
- 无效 / 不存在的 task_id 给友好提示（复用接口已有「未找到回测任务」错误）。
- 保留手动新建入口（无 query 时行为不变）。

## 依赖

- [003 — 定投回测](./003-dca-compute-engine.md)、[007 — MA120 策略](./007-ma120-strategy-backtest.md)、[011 — 首页改版](./011-home-redesign.md)
