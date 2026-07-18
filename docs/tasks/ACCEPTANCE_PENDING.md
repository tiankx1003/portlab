# 验收待确认事项（012–017）—— 最终态

实现期间按「推荐方案先行 + 阻塞项跳过并记录」执行。本文为收尾状态：**仅 016 一项仍待处理**，其余已确认接受并落地。

---

## ✅ 已确认接受并落地（无需再议）

下述设计决策均已按推荐方案实现、测试通过：

| 项 | 决策 |
|---|---|
| **012** 表单回填 | 前端解析 task_id 回填（不扩展后端 summary） |
| **015** 左轴单位 | 用「累计涨幅%」做 0 线镜像（价格% 与回撤% 同轴对称） |
| **015** 阈值拖动 | `range` 滑块，松手重算 |
| **015** 卖出规则 | 新高（回撤归 0）一次性清仓 |
| **015** 基准对齐 | 510300 与主标的交易日长度一致才叠加 |
| **017** 主力信号 | ETF 无 Tushare 主力接口 → 降级；份额变动 + 北向两路可用 |
| **C1** 市场概览跟随开关 | ✅ 已落地：`services/market.py` 改用 `resolve_source`，概览读对应源表（与刷新一致） |

---

## ⚠️ 仍待处理：016 估值温度计（数据源阻塞）

- **实现**：`services/valuation.py`（`percentile` 已测）+ `GET /api/valuation?symbol=`，按指数名查 `stock_index_pe_lg`。
- **阻塞**：`stock_index_pe_lg` 依赖 `py_mini_racer` 原生 `.so`，容器（**aarch64**）内该二进制缺失。
- **已尝试修复（均未成功）**：
  1. `uv pip install --upgrade py-mini-racer` → 容器**无法连 pypi.org**（TLS handshake EOF）。
  2. 清华镜像 `--force-reinstall` → **403 Forbidden**；普通安装提示已是最新但二进制仍缺。
  3. 换非 JS 的 PE 源：`index_value_hist_funddb` / `stock_zh_index_pe_lg` 在**本 akshare 版本均不存在**。
- **结论**：当前环境（aarch64 + 无外网 + 旧 akshare）无法跑通。接口返回 `available=false` + 修复方向，不报错。前端组件未做（无数据可渲染）。
- **修复路径（任选其一，需在能联网/对应架构环境）**：
  1. 在 **x86_64** 主机重建后端镜像（py_mini_racer 有 x86 二进制 wheel）；
  2. 升级 akshare 到含 `index_value_hist_funddb`（非 JS）版本 + 联网，并改 `services/valuation.py` 用该源；
  3. 联网主机预装含二进制的 `py_mini_racer` 固化进镜像。

---

## 数据源语义（已统一）
- 回撤看板（015）、回测（003/007）、市场概览（011）现均随开关 `resolve_source` 读对应源表。
- ETF 流向（017）、Tushare 拉取（009/013）需 Tushare 开关开启 + Token 有效。

## 测试总览
- 单测：013（4）、015（1）、016 percentile（1）全过。
- 接口 curl：012–017 + recent/release-notes/roadmap 全部 200；017 实测返回真实 Tushare 数据。
- 前端 `vue-tsc + build` 通过（含 `/drawboard`、`/etf-flow` 新页）。
- 后端 ruff：新代码 clean（仅余全项目既有 B008 / validation handler 长行基线）。
