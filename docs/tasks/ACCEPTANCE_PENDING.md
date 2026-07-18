# 验收待确认事项（012–017）—— 全部完成 ✅

012–017 全部实现并验证通过，**无待确认项**。下述为收尾记录。

## 已确认接受并落地

| 项 | 决策 |
|---|---|
| **012** 表单回填 | 前端解析 task_id 回填（不扩展后端 summary） |
| **015** 左轴单位 | 用「累计涨幅%」做 0 线镜像 |
| **015** 阈值拖动 | `range` 滑块，松手重算 |
| **015** 卖出规则 | 新高（回撤归 0）一次性清仓 |
| **015** 基准对齐 | 510300 与主标的交易日长度一致才叠加 |
| **017** 主力信号 | ETF 无 Tushare 主力接口 → 降级；份额变动 + 北向两路可用 |
| **C1** 市场概览跟随开关 | ✅ 已落地：概览随 `resolve_source` 读对应源表 |

## 016 估值温度计 —— 已解决 ✅

- **根因**：旧版 `py_mini_racer`（无 `__version__`）在 **aarch64** 上把原生库存成 `armlibmini_racer.glibc.so`，但加载器找 `libmini_racer.glibc.so` → 文件名对不上、加载失败，`stock_index_pe_lg` 报 "Native library not available"。**不是网络/未安装问题**（二进制本来就在）。
- **修复**：补一条软链 `libmini_racer.glibc.so -> armlibmini_racer.glibc.so`，并在 `main.py` 启动自愈（`_ensure_py_mini_racer_lib`）自动补链，重启/重建后保持。
- **验证**：`MiniRacer().eval("1+1")==2`；`/api/valuation?symbol=000300` 返回 沪深300 当前 PE 13.54、历史分位 53.4%（min 8.1 / max 65.32，截至 2026-07-17）；中证500 PE 29.96 / 分位 57.7%。
- **前端**：`ValuationView.vue`（`/valuation`，导航「估值」）—— 温度计仪表（分位→红黄绿热度）+ PE 历史折线 + 当前 PE 标线 + 指标卡片。

## 数据源语义（已统一）
- 回撤看板（015）、回测（003/007）、市场概览（011）均随开关 `resolve_source` 读对应源表。
- ETF 流向（017）、Tushare 拉取（009/013）、估值 PE（016，乐咕乐股源）需对应数据可达。

## 测试总览
- 单测：013（4）、015（1）、016 percentile（1）全过。
- 接口：012–017 + recent/release-notes/roadmap/valuation 全部 200；017 / 016 实测返回真实数据。
- 前端 `vue-tsc + build` 通过（含 `/drawboard`、`/etf-flow`、`/valuation` 三新页）。
- 后端 ruff：新代码 clean（仅余全项目既有 B008 / validation handler 长行基线）。
