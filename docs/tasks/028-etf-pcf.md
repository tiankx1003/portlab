# 028 — ETF PCF 申购赎回清单（爬虫入库 + 流向联动 + 按需懒加载）

## 目标

把 ETF **申购赎回清单（PCF，Portfolio Composition File）**纳入 PortLab，三件事一件套：

1. **爬虫入库**：华宝（fsfund，MD5 签名）/ 华泰柏瑞（huatai_pb，无签名）两家基金公司 PCF
   爬虫，成份券篮子 + 基金级头部落库。
2. **流向联动**：与 017（ETF 资金流向）打通——份额变动（申赎**结果**）× PCF 篮子（申赎**配方**）
   × 最小申赎单位 → 估算每只成份股因当日净申赎被净买/净卖的股数与金额，看板新增
   「成份股申赎压力」区块，把宏观份额信号下沉到成份股层面。
3. **按需懒加载**：点击加载时若库无该 ETF 的 PCF（或过期）自动抓取入库，**自动发现数据源**，
   免手动跑爬虫（与 ensure_price_data / ensure_etf_shares 一致）。

## 依赖

- [017 — ETF 资金流向图表](./017-etf-fund-flow.md)（看板入口、Tushare `fund_share` 份额）
- [002 / 009] 数据拉取（`storage` UPSERT、`ensure_*` 缺口补拉范式）

## 数据模型（多源统一宽表，新建）

### `raw_pcf_basket`（成份券篮子，每只股票一行）
PK `(source, fund_code, trading_day, stock_code)`，`source = fsfund/huatai_pb/...`。
字段取两家并集：基金信息（fund_name/fund_codes/fund_id/scid）、成份股（stock_short/gpsc/stock_codesrc）、
数量金额（number/tdje/sgtdje/shtdje）、比例（yjbl/sg_yjbl/sh_zjbl/discount_rate/premium_rate）、
标志（tdbz/buyorsell/mmbz）、华宝独有（record_id/reserved/procflag）。加新公司只加行。

### `raw_pcf_day_info`（基金级头部，每 基金×日期 一行）
PK `(source, fund_code, trading_day)`；nav/cash_component/creation_redemption_unit（最小申赎单位）/
creation_limit/redemption_limit/...。华宝无头部 → 该源此表无行。

### `raw_etf_share_daily`（ETF 每日份额，Tushare `fund_share`）
PK `(symbol, trade_date)`；`fd_share` 万份（绝对值，连续两日算 `shares_change`）。

## 衍生口径（成份股申赎压力）

- `net_units = shares_change(万份) × 10000 / creation_redemption_unit(份)` —— 净申赎单位数
- `est_shares = net_units × number` —— 成份股估算买卖股数（带方向，正=净买/红、负=净卖/绿）
- `est_amount = net_units × tdje` —— 估算金额（PCF 替代金额近似；tdje 缺则空）
- 现金替代券（`tdbz` 含「现金」）标注类型、股数灰显（非实物股票流动）
- 边界降级：无 PCF / 缺最小单位（`DEFAULT_CRU` 兜底常见 ETF）/ 缺份额连续两日 → `available=false`

## 按需懒加载（核心）

`ensure_pcf_data(db, symbol)`（`pcf_data.py`，仿 `ensure_price_data`）：
- **已知 source + 新鲜**（最近 `trading_day ≥ today−3`）→ 跳过
- **已知 source + 过期** → 补抓 `(最近日, today]`
- **未知 source（库无）** → 按 `SOURCES = ["huatai_pb","fsfund"]` 优先级抓最近 5 天试探，命中即入库
  （**自动发现，无需维护 ETF→公司映射**；入库后库记 source，走快路径）

爬虫核心抽到 `app/services/pcf_crawlers.py`（`fetch_pcf_day(source, fund_code, day)` 统一接口），
CLI（`scripts/pcf/`）与懒加载共用，单一真相。

## 文件

- **新建**：`models/pcf.py`、`models/etf_share.py`；`services/pcf_ingest.py`（映射+入库，去千分位逗号）、
  `pcf_crawlers.py`、`pcf_data.py`、`pcf_pressure.py`、`etf_share_data.py`；`api/pcf_pressure.py`；
  `scripts/pcf/`（crawl_fsfund_pcf / crawl_huatai_pb_pcf / ingest_pcf_csv / README）；
  `mysql/init/13_pcf.sql` + `14_etf_share.sql`、`migrations/014_pcf.sql` + `015_etf_share.sql`
- **修改**：`services/storage.py`（`upsert_etf_shares`）、`main.py`（router 注册 + `_ensure_pcf_tables` 自愈）、
  `models/__init__.py`；前端 `api/index.ts`（PcfPressure 类型 + `getPcfPressure`）、
  `views/EtfFlowView.vue`（联动区块 + 默认标的 512890）

## 验证

- 爬虫入库：`crawl_huatai_pb_pcf.py --codes 512890 --db` → 500 basket + 10 day_info
- 联动：512890 `net_units=-42`（份额 −4200 万份 ÷ 最小单位 100 万），50 只成份股净卖出，手算核对一致
- 懒加载：删库 → 点加载自动发现 `huatai_pb` 抓取入库；非两家（510050 华夏）两源试后空降级
- 修复：PCF 金额千分位逗号致入库 NULL、爬虫 `--db` 的 `import app` 路径
