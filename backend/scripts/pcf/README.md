# ETF 申购赎回清单 (PCF) 爬虫

按需抓取各家基金公司官网公布的 ETF 申购赎回清单（Portfolio Composition File，
PCF / 成份券篮子），落盘为 CSV，供后续分析/校验使用。

本目录是**离线 CLI 工具**（纯标准库，无第三方依赖），与运行时 `app/services/fetcher/`
体系无关：需要时手动跑一次，把产出的 CSV 放进 `exports/`（已被 `.gitignore` 忽略）。

## 目录结构

```
backend/scripts/pcf/
├── crawl_fsfund_pcf.py       # 华宝基金 (fsfund)   —— 需 MD5 签名
├── crawl_huatai_pb_pcf.py    # 华泰柏瑞 (huatai-pb) —— 无签名，stockList + dayInfo 双表
├── ingest_pcf_csv.py         # 现成 CSV → MySQL 入库
└── README.md
```

## 运行方式

统一在 `backend/` 目录下用 `uv run --no-sync python scripts/pcf/xxx.py ...` 运行。
两个脚本参数同构：`--codes` / `--codes-file`（二选一）+ `--start` + `--end`，外加
`--out` `--delay` `--retries` `--cn`（中文表头）`--append`（追加、不写表头）。

```bash
cd backend

# 华宝基金：562060、562090 两只 ETF 某段时间的清单
uv run --no-sync python scripts/pcf/crawl_fsfund_pcf.py \
    --codes 562060,562090 --start 2026-06-15 --end 2026-06-22 \
    --out exports/pcf_fsfund.csv --cn

# 华泰柏瑞：512890 的清单 + 基金级 dayInfo（净值/现金差额/申赎上限等）
uv run --no-sync python scripts/pcf/crawl_huatai_pb_pcf.py \
    --codes 512890 --start 2026-07-01 --end 2026-07-30 \
    --out exports/pcf_huatai_pb.csv \
    --day-info exports/pcf_huatai_pb_dayinfo.csv
```

基金代码清单也可从文件读（每行一个，`#` 开头为注释）：

```bash
uv run --no-sync python scripts/pcf/crawl_fsfund_pcf.py \
    --codes-file codes.txt --start 20260615 --end 20260622
```

> 日期参数同时支持 `YYYYMMDD` 与 `YYYY-MM-DD`。`--append` 便于把多批结果合并到同一文件。
> 默认输出路径已设为 `exports/...`，脚本会自动创建该目录。

## 各家逆向要点

抓 PCF 没有"行业标准接口"，每家基金公司的接口形态都不一样。下表是这两家的关键差异，
新增第三家时先摸清这几项再动手。

| 维度 | 华宝 fsfund | 华泰柏瑞 huatai-pb |
|---|---|---|
| 端点 | `POST api.fsfund.com/v2/webzk/queryController/getFundShareInfo` | `POST www.huatai-pb.com/etf-web/etf/index.json` |
| 请求体 | JSON（`fundCode`/`netNo=web`/`timestamp`/`startDate`） | `application/x-www-form-urlencoded`（`fundcode`/`beginDate`） |
| 鉴权 | **MD5 签名**（见下） | 无签名；`insert_cookie` 当前非必需，`--cookie` 留作反爬升级后备 |
| 日期格式 | `YYYYMMDD` | `YYYY-MM-DD` |
| 成功判定 | `code == "0000"` | `status == "success"` |
| 返回结构 | `data[]`（每条一只股票） | `stockList[]`（成份券）+ `dayInfo`（基金级头部） |
| 交易日来源 | 入参 `startDate` | `stockList[0].tradingday`（毫秒戳、东八区），回退 `maxDate` |

**华宝签名算法**（逆向自 `www.fsfund.com/static/js/common/common.js` 的 `addSignature`）：

1. 强制 `netNo='web'`，`timestamp` = 当前毫秒时间戳；
2. 过滤空值（`None` / `""` / `"null"`）；
3. 参与签名的 key 按 ASCII 字典序升序；
4. 拼成 `k1=v1&k2=v2&...&`（每对后都带 `&`），末尾追加 `key=CD364559FDA24D53B05F01E943ECDFCC`（无前导 `&`）；
5. 对整串做 MD5，作为 `signature` 字段随请求一起发。

实现见 `crawl_fsfund_pcf.py::make_signature`。

### 输出字段（CSV 列）

- **华宝** 单表，列见 `crawl_fsfund_pcf.py::COLUMNS`（基金/股票信息、数量金额、比例、标志等，共 20 列）。
- **华泰柏瑞** 双表：成份券篮子 `COLUMNS`（18 列）+ 基金级 `DAY_INFO_COLUMNS`（20 列，含净值、现金差额、最小申赎单位、申赎上限、标的指数等）。
- 加 `--cn` 即输出中文表头（见各文件的 `CN_HEADER`），默认输出英文字段名。

## 网络与抓取注意

- 这两个端点是**外部基金公司官网**，与项目"东财数据 API 阻断"的约束无关，但本机能否访问
  `fsfund.com` / `huatai-pb.com` 视网络环境而定，跑之前先确认可达。
- 默认 `--delay 0.3s` 限速、`--retries 3` 带线性退避，**请勿调小 delay 或并发轰炸**，
  以免被风控封禁。单条 (基金×日期) 失败只会打 `✗` 跳过，不中断整批。
- 非交易日 / 未来日期返回空数组属正常，脚本会统计"无数据"组合数。

## 入库 MySQL

成份券与基金级头部统一存两张宽表，用 `source` 列区分来源（fsfund/huatai_pb/...），
跨公司可比、加新公司只加行（仅出现全新字段才 ALTER 加列）。

| 表 | 主键 | 说明 |
|---|---|---|
| `raw_pcf_basket` | (source, fund_code, trading_day, stock_code) | 成份券篮子，两家字段并集 |
| `raw_pcf_day_info` | (source, fund_code, trading_day) | 基金级头部（净值/现金差额/申赎上限）；华宝无 → 不入 |

- 模型：`backend/app/models/pcf.py`（`RawPcfBasket` / `RawPcfDayInfo`）
- 入库逻辑：`backend/app/services/pcf_ingest.py`（CSV 列名→DB 列名映射 + 类型转换 + 按 `(源,基金,日期)` 先删后写幂等）

### 建表（迁移，项目惯例双轨）

- **fresh 安装**：`mysql/init/13_pcf.sql` —— MySQL 容器首次初始化（数据目录为空）时自动执行。
- **已部署库升级**：`mysql/migrations/014_pcf.sql` —— 手动执行一次：
  ```bash
  docker exec -i portlab-mysql mysql -uroot -p"$MYSQL_ROOT_PASSWORD" portlab \
      < mysql/migrations/014_pcf.sql
  ```

### 方式一：抓取时直接入库（爬虫 `--db`）

两个爬虫都支持 `--db`，抓取后顺带写 MySQL（延迟 import，不带此开关仍是纯 stdlib 离线脚本）：

```bash
# 华宝：抓 + 入库（同时仍写 CSV）
uv run --no-sync python scripts/pcf/crawl_fsfund_pcf.py \
    --codes 562060 --start 2026-06-15 --end 2026-06-22 --db

# 华泰柏瑞：抓 + 入库（成份券 + 头部；头部入库不依赖 --day-info 文件）
uv run --no-sync python scripts/pcf/crawl_huatai_pb_pcf.py \
    --codes 512890 --start 2026-07-01 --end 2026-07-30 --db
```

### 方式二：现成 CSV 入库（`ingest_pcf_csv.py`）

历史 CSV 回填、或别处产生的 CSV：

```bash
# 华宝成份券 CSV（英文表头，爬虫默认）
uv run --no-sync python scripts/pcf/ingest_pcf_csv.py \
    --source fsfund --basket exports/pcf_fsfund.csv

# 华泰柏瑞 成份券 + 头部（中文表头加 --cn）
uv run --no-sync python scripts/pcf/ingest_pcf_csv.py \
    --source huatai_pb --basket exports/pcf_huatai_pb.csv \
    --day-info exports/pcf_huatai_pb_dayinfo.csv --cn
```

> 幂等：同一 `(source, 基金, 交易日)` 重跑先删后写；主键缺失的行（如 stock_code 空）跳过并计数。
> 类型转换：空串→NULL、金额/比例→DECIMAL、日期支持 YYYYMMDD 与 YYYY-MM-DD。

## 如何新增一家基金公司的 PCF 爬虫

以 `crawl_huatai_pb_pcf.py` 为模板（它比华宝多一张 dayInfo 表，结构更通用），
照下面七步改即可。两个现有脚本刻意保持**自包含**，就是为了方便整文件复制后改写。

1. **建文件** `crawl_<公司简称>_pcf.py`，复制 `crawl_huatai_pb_pcf.py` 全文。
2. **摸接口**：浏览器 DevTools 打开该公司 ETF 的 PCF 页，找到返回成份券的 XHR，
   记下 URL、Method、Content-Type、请求体字段、是否需要签名/cookie。
3. **改常量**：`API` / `SITE` / `UA`，以及（若有）签名 key、时区。
4. **改 `fetch_one`**：拼请求体、构造 headers、判定成功（`code` 还是 `status`）、
   返回原始响应 dict。保留带退避的重试循环。
5. **改字段映射**：定义 `COLUMNS`（输出列）+ `STOCK_KEY`（输出列名 → 接口 JSON key）
   + `CN_HEADER`（中文名）。若接口区分成份券/基金头部，照搬 `DAY_INFO_*` 那套再加一张表。
6. **改 `normalize_*`**：把一条原始记录补齐成统一列、`None→""`；交易日取值规则
   （直接用入参，还是从毫秒戳 `ms_to_date` 转换）写清楚。
7. **改 `parse_args`** 的 `--out` 默认值（`exports/pcf_<公司简称>.csv`）与 `description`，
   并更新模块 docstring 的"接口要点"与"用法"。

落地后在本 README 的「各家逆向要点」表格补一行即可。

**入库映射**：新公司要入库时，在 `app/services/pcf_ingest.py` 的 `BASKET_FIELD_MAP`
（若有头部再加 `DAYINFO_FIELD_MAP`）补一条 `{新source: {csv列名: db列名}}`；若出现
`raw_pcf_basket` 没有的全新字段，需同步在 model + `init/13_pcf.sql` + `migrations/014_pcf.sql`
加列（已有字段直接复用、缺的填 NULL）。之后爬虫 `--db` 或 `ingest_pcf_csv.py --source 新source`
即可入库，无需改其他代码。
