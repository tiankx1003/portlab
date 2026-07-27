# 025 — 修复 POST 创建接口的幂等命中 return 缩进 bug

## 目标

修复 `backend/app/api/` 下 3 个 POST 创建类接口的同源控制流 bug：**幂等命中检查后的 `return` 语句未缩进进 `if` 块内**，导致无论命中与否都直接返回 task_id，后续的补数据 / 计算 / 落库代码全部不可达。

修复后，POST 创建链路（创建 → 落库 → 用 task_id 取 chart/summary）恢复正常，是 [026 — MCP Server](./026-mcp-server.md) 回测类 tool 能用的**前置条件**。

---

## Bug 根因与影响

### 根因

形式如下（以 ma120 为例）：

```python
if db.get(ResultMa120Summary, task_id) is not None:
    log_save(db, task_id, "ma120", req.symbol)
return ApiResponse.ok(data=Ma120Created(task_id=task_id))   # ← 4 空格缩进，在 if 块外！
                                                            #   应为 8 空格（收进 if 块内）

fetch_start = ...        # ← 以下全部不可达
ensure_price_data(...)
run_backtest(...)
log_save(...)
return ApiResponse.ok(...)
```

`return` 语句是 4 空格缩进（与 `if` 同级），而不是 8 空格（在 `if` 块内）。Python 不会对「不可达代码」报错，所以语法合法、能跑、CI 不挂，但语义完全错。

### 影响

- 用户调 `POST /api/backtest/ma120`（或 grid / drawboard save），后端**立刻返回 task_id**，但不计算、不落库。
- 紧接着调 `GET /ma120/{task_id}/chart` 或 `/summary`，必然返回「未找到回测任务 xxx」。
- 整条「先创建、后查看」的链路对**新参数**完全断开；只有命中别人早就算过的旧 task_id（手工触发或历史遗留）才能正常取结果。
- 前端「开始回测」按钮点了等于没点；MCP 的 `run_*_backtest` tool 调了也拿不到真实回测。

### 修复历史与同源扩散

- `backtest.py` 的 `create_dca_backtest` 已于 commit `2859567`（2026-07-27）修复。commit message 写「与 create_ma120_backtest 语义一致」——但**作者把 ma120 当成正确参照**，而 ma120 本身就有同样 bug。这是典型的「拿病号当健康参照」导致同源 bug 扩散未被发现。
- 复制粘贴从 ma120 → grid → drawboard 传播，三处 bug 完全同构。

---

## 核查结论（已完成，供修复参考）

> 已对 `backend/app/api/` 下全部 12 个 POST 函数核查（不只 3 个有问题的）。结论：

| 文件 | 函数 | 路由 | 缓存检查 return 缩进 | 结论 |
|------|------|------|---------------------|------|
| `backtest.py` | `create_dca_backtest` | POST /dca | ✅ 在 if 块内（8 空格） | ✅ **已修复**（commit 2859567） |
| `backtest.py` | `preview_dca_backtest` | POST /dca/preview | —（预览不落库，无幂等检查） | ✅ 正常 |
| `ma120.py` | `create_ma120_backtest` | POST /ma120 | ❌ **在 if 块外（4 空格）** | ❌ **待修（本任务）** |
| `ma120.py` | `preview_ma120_backtest` | POST /ma120/preview | —（预览不落库） | ✅ 正常 |
| `grid.py` | `create_grid` | POST /grid | ❌ **在 if 块外（4 空格）** | ❌ **待修（本任务）** |
| `grid.py` | `preview_grid` | POST /grid/preview | —（预览不落库） | ✅ 正常 |
| `portfolio.py` | `create_portfolio` | POST /portfolio | ✅ 在 if 块内（8 空格） | ✅ 正常 |
| `drawboard.py` | `save` | POST /save | ❌ **在 if 块外（4 空格）** | ❌ **待修（本任务）** |
| `event_dashboard.py` | `smart_match_endpoint` | POST /smart-match | —（无幂等模式） | ✅ 正常 |
| `event_dashboard.py` | `create_event` | POST "" | —（无幂等模式） | ✅ 正常 |
| `feedback.py` | `create_feedback` | POST "" | —（无幂等模式） | ✅ 正常 |
| `data.py` | `fetch_prices` | POST /fetch | —（无幂等模式） | ✅ 正常 |

**待修：3 处。其余 9 处正常。**

---

## 依赖

- [007 — 红利 MA120 策略回测](./007-ma120-strategy-backtest.md)（ma120 创建接口的来源）
- [020 — 网格交易策略回测](./020-grid-trading.md)（grid 创建接口的来源）
- [019 — drawboard v2](./019-drawboard-v2.md)（drawboard save 接口的来源）
- [002 — 数据拉取模块](./002-data-fetcher.md)（`ensure_price_data` 补缺范式）
- 反向被依赖：[026 — MCP Server](./026-mcp-server.md)（MCP 回测类 tool 验收依赖本任务）

---

## Part A：修复方案

### 修复点 1：`backend/app/api/ma120.py` — `create_ma120_backtest`

**当前（L70-73，buggy）**：

```python
    # 幂等命中：同参数已算过则直接返回 task_id
    if db.get(ResultMa120Summary, task_id) is not None:
        log_save(db, task_id, "ma120", req.symbol)
    return ApiResponse.ok(data=Ma120Created(task_id=task_id))
```

**修复后**：

```python
    # 幂等命中：同参数已算过则直接返回 task_id，跳过重复计算与重复拉取
    if db.get(ResultMa120Summary, task_id) is not None:
        log_save(db, task_id, "ma120", req.symbol)
        return ApiResponse.ok(data=Ma120Created(task_id=task_id))

    # 未命中：回溯补数据 → 计算 → 落库 → 返回
    fetch_start = ...
```

**改动**：把 L73 的 `return` 行向右缩进 4 空格（4 → 8 空格），收进 `if` 块内。在其后加一行注释说明「未命中：继续计算落库」。

**复活的死代码（L75-89）**：补数据 + 基准行情 + `run_backtest` + `log_save` + 末尾 `return`——修复后全部可达。

### 修复点 2：`backend/app/api/grid.py` — `create_grid`

**当前（L61-63，buggy）**：

```python
    if db.get(ResultGridSummary, task_id) is not None:
        log_save(db, task_id, "grid", req.symbol)
    return ApiResponse.ok(data=GridCreated(task_id=task_id))
```

**修复后**：

```python
    # 幂等命中：同参数已算过则直接返回 task_id
    if db.get(ResultGridSummary, task_id) is not None:
        log_save(db, task_id, "grid", req.symbol)
        return ApiResponse.ok(data=GridCreated(task_id=task_id))

    # 未命中：补数据 → 计算 → 落库
    err = ensure_price_data(...)
```

**改动**：把 L63 的 `return` 行向右缩进 4 空格。grid.py 当前命中分支上方没有注释，顺手补一行注释对齐其他接口风格。

### 修复点 3：`backend/app/api/drawboard.py` — `save`

**当前（L95-98，buggy）**：

```python
    # 幂等命中：同参数已算过则直接返回 task_id
    if db.get(ResultDrawboardSummary, task_id) is not None:
        log_save(db, task_id, "drawboard", req.symbol)
    return ApiResponse.ok(data=DrawboardSaved(task_id=task_id))
```

**修复后**：

```python
    # 幂等命中：同参数已算过则直接返回 task_id，跳过重复计算
    if db.get(ResultDrawboardSummary, task_id) is not None:
        log_save(db, task_id, "drawboard", req.symbol)
        return ApiResponse.ok(data=DrawboardSaved(task_id=task_id))

    # 未命中：补数据 → 计算 → 落库
    err = ensure_price_data(...)
```

**改动**：把 L98 的 `return` 行向右缩进 4 空格。

### 三处共同特征

- 都是同一个修复动作：`return` 行缩进 4 → 8 空格。
- 都是复制粘贴从 ma120 扩散出来的同源 bug。
- 修复后 `preview_*` 接口（`run_realtime` 不落库路径）保持不变，可以继续作为「实时预览」语义。
- 不需要改任何 schema、模型、计算逻辑——只改控制流缩进。

---

## Part B：验证

### 1. 语法校验

每个文件改完后跑：

```bash
python -c "import ast; ast.parse(open('backend/app/api/ma120.py').read())"
python -c "import ast; ast.parse(open('backend/app/api/grid.py').read())"
python -c "import ast; ast.parse(open('backend/app/api/drawboard.py').read())"
```

### 2. 端到端验证（需 docker compose up backend + mysql）

对每个修复的接口走「创建 → 取 summary」链路：

```bash
# MA120：用一组全新参数（确保不命中缓存）
TASK=$(curl -s -X POST http://localhost:8010/api/backtest/ma120 \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"510880","start_date":"2023-01-01","end_date":"2024-01-01","capital_mode":"fixed","principal":100000,"splits":10,"ma_period":120}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['task_id'])")
echo "task_id: $TASK"

# 取 summary：修复前会报「未找到回测任务」，修复后返回完整指标
curl -s "http://localhost:8010/api/backtest/ma120/$TASK/summary"
```

对 grid（POST /api/backtest/grid）和 drawboard（POST /api/drawboard/save）同样验证。

### 3. 幂等性回归

同一参数连调两次 POST：
- 第一次：未命中缓存 → 应触发 `ensure_price_data` + `run_backtest`（可在 backend 日志看到拉数和计算）。
- 第二次：命中缓存 → 应直接返回相同 task_id，不再拉数计算（日志无新动作）。
- 两次返回的 task_id 必须相同。

### 4. preview 路径不受影响

```bash
# preview 不落库，修复前后行为应完全一致
curl -s -X POST http://localhost:8010/api/backtest/ma120/preview \
  -H 'Content-Type: application/json' \
  -d '{...}'
```

---

## Part C：附带的一致性观察（可选，非本任务必需）

核查中发现 `portfolio.py` 的 `create_portfolio`（L63-64）在缓存命中分支**没有调用 `log_save`**，与其他 4 个落库型 POST（dca/ma120/grid/drawboard 命中分支都有 `log_save`）行为不一致：

```python
# portfolio.py 当前
if db.get(ResultPortfolioSummary, task_id) is not None:
    return ApiResponse.ok(data=PortfolioCreated(task_id=task_id))   # 没有 log_save
```

后果：组合回测命中缓存时，[012 — 回测直达](./012-backtest-deeplink.md) 的「最近保存记录」不刷新「最近保存时间」。不影响落库正确性，仅影响 recent 列表的时效。

**本任务不强制修**（不是 bug，是功能差异）。若想统一行为，可在命中分支 return 前补一行：

```python
log_save(db, task_id, "portfolio", ",".join(req.symbols))
```

列为可选改动，由实施者决定。

---

## 验收标准

- [ ] `ma120.py` L73 `return` 收进 if 块内（8 空格）
- [ ] `grid.py` L63 `return` 收进 if 块内（8 空格）
- [ ] `drawboard.py` L98 `return` 收进 if 块内（8 空格）
- [ ] 三个文件 `python -c "import ast; ast.parse(...)"` 语法校验通过
- [ ] MA120 创建 → summary 链路通：新参数 POST 后 GET summary 返回完整指标（不再是「未找到回测任务」）
- [ ] Grid 创建 → summary 链路通
- [ ] Drawboard save → summary 链路通
- [ ] 幂等性：同参数二次 POST 返回相同 task_id，不重复拉数计算
- [ ] preview 路径行为不变（不受本修复影响）
- [ ] portfolio 接口未改（若实施者选择补 log_save，单独说明）

---

## 不做的事

- 不改 schema / 模型 / 计算逻辑（只改控制流缩进）
- 不动 `preview_*` 接口（其控制流本来就对）
- 不重构幂等模式（如抽公共函数）——最小化改动，3 行缩进修复
- 不改 portfolio（除非实施者选择补 log_save，作为可选改动）
- 不动前端（前端本来就期待「创建 → 取结果」链路，bug 修复后自然通）

---

## 开放问题

- [ ] **抽公共「幂等创建」装饰器/工具函数**：5 个 POST 创建接口（dca/ma120/grid/portfolio/drawboard）的幂等模式高度同构，可抽 `create_or_cache(db, summary_model, task_id, log_kind, symbol, compute_fn)`。本期不做（最小化修复优先），列为后续重构。
- [ ] **加自动化测试防回归**：当前没有 POST 创建链路的端到端测试，bug 存活多周才被发现。建议加 pytest 用例：POST 创建 → GET summary → 断言非「未找到」。可结合 002 的测试范式。
- [ ] **lint 规则检测不可达代码**：ruff 有 `UP004`/`F401` 等，但检测「函数体内 return 之后的代码」需要专门规则。可调研 ruff 自定义规则或 pyright 的 reachability 检查。
