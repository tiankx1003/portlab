# PortLab — Task Index

任务详情见 `docs/tasks/` 目录下的独立文档。状态：☑ 已完成 / ☐ 未实现。

| # | 任务 | 摘要 | 状态 |
|---|------|------|------|
| 001 | [项目基础设施搭建](docs/tasks/001-project-infrastructure.md) | FastAPI + MySQL + Vue3 + Docker 骨架 | ☑ |
| 002 | [数据拉取模块](docs/tasks/002-data-fetcher.md) | DataFetcher 抽象 + AkShare（东财/腾讯回退） | ☑ |
| 003 | [定投回测：计算引擎、API 与前端](docs/tasks/003-dca-compute-engine.md) | DCA 计算、XIRR 年化、图表与汇总 | ☑ |
| 004 | [联调、收尾与文档](docs/tasks/004-integration-and-release.md) | 端到端联调与发布收尾 | ☑ |
| 005 | [UI 优化与标的信息增强](docs/tasks/005-ui-and-symbol-enhancement.md) | 标的搜索、名称解析、图表打磨 | ☑ |
| 006 | [智能定投（均线定投策略）](docs/tasks/006-smart-dca.md) | 均线偏离度动态扣款率 | ☑ |
| 007 | [红利 MA120 策略回测](docs/tasks/007-ma120-strategy-backtest.md) | MA120 金字塔分批买卖策略全链路 | ☑ |
| 008 | [问题反馈](docs/tasks/008-feedback.md) | 右上角反馈图标，Markdown 提交，保留 3 天 | ☑ |
| 009 | [Tushare 数据源扩展](docs/tasks/009-tushare-data-source.md) | 可选 Tushare 数据源，开关启用，行情独立成表 | ☑ |
| 010 | [更新日志（Release Notes）功能](docs/tasks/010-release-notes.md) | 导航栏铃铛图标，展示最新 5 条变更 + GitHub 入口 | ☑ |
| 011 | [首页改版](docs/tasks/011-home-redesign.md) | 首页重设计为工具箱门户 + 导航品牌区可点击 | ☑ |
| 012 | [回测结果直达（URL ?task= 预载）](docs/tasks/012-backtest-deeplink.md) | 回测页支持 ?task= 直载结果，首页最近记录可点达 | ☑ |
| 013 | [Tushare 限频治理与分段拉取](docs/tasks/013-tushare-rate-limit.md) | 长区间分段、节流、重试、积分提示 | ☑ |
| 014 | [更新日志管理（脚本 / CLI）](docs/tasks/014-release-notes-admin.md) | 免 SQL 维护更新日志：CLI / 轻量 API 增删改 | ☑ |
| 015 | [基于最大回撤的买入策略看板](docs/tasks/015-drawdown-buy-strategy.md) | 拖拽回撤阈值定义买点，左轴价格/回撤镜像 + 右轴市值/收益 | ☑ |
| 016 | [估值温度计 / 估值分位看板](docs/tasks/016-valuation-thermometer.md) | 指数 PE 历史分位 + 温度计仪表（乐咕乐股源） | ☑ |
| 017 | [ETF 资金流向图表](docs/tasks/017-etf-fund-flow.md) | ETF 份额/北向/主力三信号（Tushare），观察国家队动向 | ☑ |
| 018 | [事件冲击产业链看板](docs/tasks/018-event-impact-dashboard.md) | 事件→标的池→产业链关系图+波动对比+相关性热力图；LLM 智能匹配（OpenAI 兼容） | ☑ |
| 019 | [drawboard v2：补齐 sell_mode + DB 持久化 + 参数纠正](docs/tasks/019-drawboard-v2.md) | 回撤看板迭代：sell_mode 三模式 + 两表幂等 + 默认值对齐 015 | ☑ |
