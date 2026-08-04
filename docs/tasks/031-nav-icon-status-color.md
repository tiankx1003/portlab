# 031 — 导航栏图标状态化配色（钥匙 / MCP，主题适配）

## 目标

让导航栏的钥匙图标（Tushare 数据源）和 MCP 图标根据状态变色，一眼可辨；
并适配明暗主题（新增主题变量，避免硬编码颜色在暗色下不可读）。

## 改动

新增两个主题变量（`App.vue` 的 `[data-theme]` 两套）：

| 变量 | light | dark | 用途 |
|------|-------|------|------|
| `--accent-gold` | `#bf8700` | `#e3b341` | 钥匙图标 Tushare 启用 |
| `--accent-green` | `#1a7f37` | `#3fb950` | MCP 图标运行中（+ 面板状态灯） |

色值借鉴 GitHub Primer 的 attention / success 色阶，两主题下对比度均达标。

- `DataSourceWidget.vue`：钥匙按钮 `.active` 的 `color` 从 `var(--primary)`（蓝）改 `var(--accent-gold)`（Tushare 启用时）
- `McpStatusWidget.vue`：
  - 图标按钮绑定 `:class="{ running: lightColor === 'green' }"`，运行中 `color: var(--accent-green)`，否则次要灰
  - 面板状态灯 `.d-green` 从硬编码 `#3ba272` 改 `var(--accent-green)`（统一颜色源 + 主题适配）
  - 按钮 `title` 动态化（hover 显示「运行中 / 未启动 / 后端未连通」）

## 附带修复

MCP 图标刷新页面后颜色不显示（组件挂载时未拉状态，只有点开面板才 load）→
补 `onMounted(load)`，与钥匙图标组件一致；刷新后图标颜色立即正确。

## 验收

- [x] Tushare 开关启用 → 钥匙图标金色；关闭 → 次要灰
- [x] MCP 运行中 → 图标绿色；非运行中 → 灰色
- [x] 刷新页面后 MCP 图标立即显示正确颜色（无需点开面板）
- [x] 明暗主题切换，金 / 绿两色自动适配（暗色下可读）
