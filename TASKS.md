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
| 020 | [网格交易策略回测](docs/tasks/020-grid-trading.md) | 中枢+间距双向触发吃震荡；图表画网格 markLine，补齐趋势/恐慌/震荡三件套 | ☑ |
| 021 | [股息率 / DCF 估值回测](docs/tasks/021-dividend-dcf-backtest.md) | 历史相同估值买入回测+胜率分布；依赖016股息率历史，PE分位降级 | ☐ |
| 022 | [组合回测（含有效前沿/最优权重）](docs/tasks/022-portfolio-backtest.md) | 多标的组合收益/回撤/波动 + 马科维茨有效前沿求最优权重 | ☑ |
| 023 | [策略擂台（横向对比）](docs/tasks/023-strategy-arena.md) | 同标的多策略/同策略多标的对比，归一化净值+指标表，消费四策略 summary | ☑ |
| 024 | [估值看板 v2：PE 通道 + 多指数叠加 + 双源补强](docs/tasks/024-valuation-v2.md) | 7 指数（lg+csindex 双源）+ PE 5 通道 + 多指数叠加归一化 + 时间窗口；补强 016 简化 MVP，4 个无数据指数灰显 | ☑ |
| 025 | [修复 POST 创建接口幂等命中 return 缩进 bug](docs/tasks/025-fix-post-create-bug.md) | ma120/grid/drawboard 三处 return 未缩进进 if 块致落库不可达；一行缩进修复 + 端到端验证 | ☑ |
| 026 | [PortLab MCP Server（API 暴露给 LLM）](docs/tasks/026-mcp-server.md) | 独立容器 + HTTP 传输，32 tool（只读+回测创建），chart 降采样 ~80 点，api-registry.yaml 契约表治理接口漂移；导航栏右上角 MCP 图标 + 状态面板（连接地址/工具列表/一键复制配置）；依赖 025 | ☑ |
| 027 | [股债比价看板](docs/tasks/027-equity-bond.md) | EP/股息率 ÷ 十年期国债；滚动均值+±1/±2/±3σ 通道（3/5/10年窗口），右轴指数点位；国债(bond_zh_us_rate)+指数点位(stock_zh_index_daily)新建表，PE 复用 024 → **并入 032，不再独立实现** | ☐ |
| 028 | [ETF PCF 申购赎回清单（爬虫入库 + 流向联动 + 懒加载）](docs/tasks/028-etf-pcf.md) | 华宝/华泰柏瑞 PCF 爬虫落库(raw_pcf_basket/day_info)；份额变动×篮子×最小申赎单位估成份股申赎压力(资金流向看板联动区块)；点击加载按需自动发现源补抓入库，免手动跑爬虫 | ☑ |
| 029 | [前端 dev server 配置化（端口 / 代理目标 / host 白名单）](docs/tasks/029-frontend-devserver-config.md) | VITE_PORT/VITE_BACKEND_TARGET/VITE_ALLOWED_HOSTS 三变量；修 VITE_BACKEND_TARGET 未透传隐患；vite.config.ts + Dockerfile + compose + .env | ☑ |
| 030 | [修复 mcp 容器在 Docker Desktop 启动失败](docs/tasks/030-fix-mcp-docker-startup.md) | ① 嵌套 bind mount 冲突（改 ./docs:/docs:ro 整目录挂载）② PYTHONPATH 缺失（src 布局补 PYTHONPATH=/app/src）；两坑被首次挂载失败掩盖，mcp 此前未在 mac 真正跑起 | ☑ |
| 031 | [导航栏图标状态化配色（钥匙 / MCP，主题适配）](docs/tasks/031-nav-icon-status-color.md) | 钥匙 Tushare 启用→金 / MCP 运行→绿、非运行→灰；新增主题变量 --accent-gold/--accent-green；修 MCP 刷新后不显色（补 onMounted） | ☑ |
| 032 | [估值与信号看板（估值重构 + 三层共振）](docs/tasks/032-valuation-signal-board.md) | 三层共振信号看板：技术估值(MA120/回撤/PE/PB/股息率/股债比价)+大类资产(全收益vs5年均线+创业板/上证比+基金发行)+资金宏观(社融/M1M2/PMI/PPI/融资融券/北向)；AkShare为主+Tushare5000积分补强；吸收027，下线016旧码，复用024数据通路 | ☑ |
