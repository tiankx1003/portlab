# 014 — 更新日志管理（脚本 / CLI）

## 目标

提供免 SQL 的更新日志维护方式：一个 CLI 脚本（或轻量管理 API），支持新增 / 列出 / 软删 / 编辑 release notes，让运营 / 开发不必直接写 SQL。

## 背景 / 动机

010 一期只做只读 GET，数据靠手写 SQL 维护（init 种子 + 手动 INSERT）。随迭代增多，纯 SQL 维护易错且门槛高。本任务补管理侧能力。

## 要点

- **CLI 脚本**（一期推荐）：`python -m app.cli.release_notes add --title ... --type feature --released-at ... --detail ...`，以及 `list / delete / restore`。
- 复用现有 `ReleaseNote` 模型与 session；软删除走 `is_deleted`。
- 可选 **管理 API**（`POST/PUT/DELETE /api/release-notes`）：一期无鉴权，仅本地 / 内网开放；引入鉴权后再公开。
- 校验 `type` 枚举、`released_at` 日期格式。

## 依赖

- [010 — 更新日志](./010-release-notes.md)
