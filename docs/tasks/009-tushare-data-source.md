# 009 — Tushare 数据源扩展

## 目标

在现有 AkShare 数据源基础上，**额外**支持 [Tushare Pro](https://tushare.pro) 作为可选行情数据源，通过一个**开关**按需启用。

- 页面右上角新增「钥匙」图标按钮，点击弹出面板，内置**开关**：关闭即用原 AkShare 免费逻辑，开启则用 Tushare；面板内可输入 / 修改 Tushare Token。
- Token 一经保存即**持久化在后端**，在主动更新或清除前一直有效，重启服务 / 容器不丢失；关闭开关不清 Token，可随时重新启用。
- Tushare 拉取的行情数据**单独写入一张新表** `raw_price_daily_tushare`，与原有 `raw_price_daily`（AkShare）物理隔离，互不污染、可分别比对。
- **避免重复拉取**：所有拉取入口（手动 `/api/data/fetch`、回测自动补数 `ensure_price_data`）统一走「先查本地表 → 仅补缺失区间 → UPSERT 写回」的幂等逻辑，优先复用已落库数据。

> 与 002（数据拉取模块）一脉相承：002 已预留 `DataFetcher` 抽象基类与 `_FETCHERS` 注册表（注释明确写明「后续可扩展更多数据源（Tushare/聚宽等）」），本任务即兑现该扩展点。

## 依赖

- [001 — 项目基础设施搭建](./001-project-infrastructure.md)
- [002 — 数据拉取模块](./002-data-fetcher.md)
- [003 — 定投回测：计算引擎、API 与前端](./003-dca-compute-engine.md)（回测引擎数据读取层需适配多源）

> 不依赖 006/007/008，但本任务适配的回测数据读取层会同时影响 DCA 与 MA120 两条回测链路。

---

## 亮点

1. **一键开关 Tushare**：导航栏钥匙面板内置开关；**关闭时完全回退原 AkShare 免费数据逻辑**，Token 原样保留，可随时重新启用，零迁移成本。
2. **Token 持久化、重启不丢**：Token 写入后端数据库后，在**主动更新或清除前永久有效**；重启服务 / 重启 Docker 容器均不丢失，开关状态同样持久。
3. **数据物理隔离、可分源比对**：Tushare 行情独立表 `raw_price_daily_tushare` 存储，与原 `raw_price_daily` 互不污染，天然支持同标的两源数据对照。
4. **零重复拉取**：所有拉取入口（手动 fetch / 回测自动补数）先查对应本地表，仅对缺失子区间发起网络请求，UPSERT 幂等写回。

---

## Part A：后端

### 1. 数据模型

#### 1.1 新表 `raw_price_daily_tushare`（Tushare 行情，与 `raw_price_daily` 隔离）

字段与 `raw_price_daily` 完全一致，仅表名不同，便于后续统一抽象：

| 字段 | 类型 | 说明 |
|------|------|------|
| symbol | VARCHAR(32) | 标的代码（PK） |
| trade_date | DATE | 交易日（PK） |
| open | DECIMAL(14,4) | 开盘价 |
| close | DECIMAL(14,4) | 收盘价 |
| high | DECIMAL(14,4) | 最高价 |
| low | DECIMAL(14,4) | 最低价 |
| volume | BIGINT NULL | 成交量（统一为「股」，见 §4 单位说明） |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |
| PRIMARY KEY (symbol, trade_date) | | 复合主键，UPSERT 幂等 |
| KEY idx_symbol_date (symbol, trade_date) | | 与原表一致 |

新建 `backend/app/models/raw_tushare.py`：

```python
class RawPriceDailyTushare(Base):
    __tablename__ = "raw_price_daily_tushare"
    # 字段与 RawPriceDaily 完全一致
```

在 `backend/app/models/__init__.py` 中注册导出 `RawPriceDailyTushare`。

#### 1.2 新表 `data_source_config`（单行配置：开关 + Token）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | TINYINT PK DEFAULT 1 | 恒为 1，单行配置 |
| tushare_enabled | TINYINT(1) NOT NULL DEFAULT 0 | **Tushare 开关**：`0`=关闭（用原 AkShare 免费逻辑），`1`=启用（用 Tushare） |
| tushare_token | VARCHAR(128) NULL | Tushare Pro Token（明文存储，见 §3 安全说明） |
| updated_at | TIMESTAMP | 默认 `CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP` |

新建 `backend/app/models/data_source_config.py`（单行配置模型），在 `models/__init__.py` 注册。

> **单行约束**：应用启动时若该表为空，自动 INSERT 一行 `id=1, tushare_enabled=0, tushare_token=NULL`（可在 `database.py` init 钩子或 `main.py` startup 中做）。
> **持久化**：开关状态与 Token 均落库，重启服务 / 重启容器后保持，不会自动失效。

### 2. SQL Migration

遵循现有 `init/`（fresh 安装）+ `migrations/`（已部署库）双写约定：

- **新建 `mysql/init/03_tushare.sql`**：`USE portlab;` 后 `CREATE TABLE IF NOT EXISTS raw_price_daily_tushare (...)` 与 `CREATE TABLE IF NOT EXISTS data_source_config (...)`（含 `id=1` 的默认行 `INSERT ... ON DUPLICATE KEY UPDATE`）。
- **新建 `mysql/migrations/004_tushare.sql`**：同样两张表 + 默认行，供已部署库手动执行。文件头按现有惯例写明「一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/03_tushare.sql 包含」。

### 3. 配置与 Token 存储

#### 3.1 后端读取 Token 的优先级

`TushareFetcher` 取 Token 顺序（先到先用）：

1. 数据库 `data_source_config.tushare_token`（UI 设置，运行时可改，**主入口**）
2. 环境变量 `TUSHARE_TOKEN`（`.env` / `docker-compose.yml`，便于无 UI 的 headless 部署引导）
3. 均无 → `FetchError("未配置 Tushare Token，请在右上角钥匙图标中设置")`

> **Token 持久化**：写入 DB 后永久有效，服务 / 容器重启不丢失；只在用户主动「更新」或「清除」时才变更。

#### 3.2 开关语义（核心）

| `tushare_enabled` | 行为 |
|-------------------|------|
| `0`（关闭，默认） | **完全回退原 AkShare 免费逻辑**：所有拉取走 `AkShareFetcher` + 写 `raw_price_daily`；Token 即便已存也**不被使用**，但保留不删 |
| `1`（启用） | 拉取走 `TushareFetcher` + 写 `raw_price_daily_tushare`；要求 Token 非空，否则回测 / fetch 返回错误 |

> **生效路由**（`resolve_source`，§5.2）：`tushare_enabled=1 且 token 非空 → 'tushare'`，否则 → `'akshare'`。开关关闭即等价于「忽略 Tushare 配置」，原有免费链路零改动可继续工作。

#### 3.3 配置文件改动（环境变量兜底）

- `backend/app/config.py` 的 `Settings` 新增：

```python
tushare_token: str = ""   # 环境变量兜底；DB 中的 Token 优先
```

- `.env.example` 新增 `TUSHARE_TOKEN=`（注释：可选，留空则在 UI 中设置）。
- `docker-compose.yml` backend 环境变量透传 `TUSHARE_TOKEN: ${TUSHARE_TOKEN:-}`。

#### 3.4 安全说明（开放项）

当前项目无鉴权体系，Token 在 DB 中**明文存储**。对本地 / 个人部署可接受；GET 接口返回时**做掩码**（仅显示后 4 位，如 `••••••••abcd`），避免整串回传前端。后续可演进为加密存储（见「开放问题」）。

### 4. TushareFetcher 实现

新建 `backend/app/services/fetcher/tushare_fetcher.py`：

```python
class TushareFetcher(DataFetcher):
    name = "tushare"
    def fetch_daily(self, symbol, start_date, end_date) -> list[PriceBar]: ...
```

#### 4.1 依赖

`backend/pyproject.toml` 的 `dependencies` 新增 `tushare`（会带入 `lxml`、`requests`、`simplejson` 等依赖）。

#### 4.2 接口与字段映射

- 使用 Tushare Pro `pro_bar` 接口拉取**前复权**日线（与 AkShare `_fetch_em` 的 `adjust="qfq"` 对齐，保证两条数据源语义一致，便于比对）：

```python
import tushare as ts
pro = ts.pro_api(token)            # token 由 §3.1 优先级解析
df = ts.pro_bar(ts_code=_to_tushare_code(symbol),
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adj="qfq", asset="E")
```

  > ETF 用 `asset="FD"`；先按 `E`（股票）尝试，空结果再退到 `FD`（基金），或根据代码首位判定（见下）。

- **ts_code 映射** `_to_tushare_code(symbol)`（与 AkShare `_to_tencent_symbol` 同源逻辑）：

| 代码首位 | 市场 | 后缀 |
|----------|------|------|
| 6 | 上交所（沪） | `.SH` |
| 5 | 上交所（ETF） | `.SH` |
| 0、3 | 深交所 | `.SZ` |
| 1 | 深交所（ETF） | `.SZ` |
| 4、8 | 北交所 | `.BJ` |

- **列映射**（Tushare 列 → `PriceBar` 字段）：

| Tushare 列 | PriceBar 字段 | 备注 |
|------------|---------------|------|
| `trade_date`（`YYYYMMDD` 字符串） | `trade_date` | 解析为 `date` |
| `open` | `open` | |
| `close` | `close` | |
| `high` | `high` | |
| `low` | `low` | |
| `vol` | `volume` | **单位换算**：Tushare `vol` 单位为「手」（=100 股），需 `× 100` 转为「股」，与 AkShare `volume`（股）对齐 |

- 复用 `base.PriceBar` 数据类，按 `trade_date` 升序返回；空结果返回 `[]`。
- 任何异常（token 无效 / 积分不足 / 网络错误 / 接口限频）统一抛 `FetchError`，消息中文友好（如「Tushare 接口调用失败：{原始 message}」，含 Tushare 返回的 `msg` 字段便于排查积分 / 权限问题）。

#### 4.3 限频与重试（一期最小实现）

- Tushare 按积分限频；一期不引入复杂限流，**单次拉取**即可。失败直接抛 `FetchError`，由上层 `ensure_price_data` 转为可读错误信息返回前端。
- 列为「开放问题」：后续可加请求间隔 / 重试 / 分段拉取（超长区间 Tushare 单次返回行数上限）。

### 5. Fetcher 注册与数据源路由

#### 5.1 注册 TushareFetcher

`backend/app/services/fetcher/__init__.py` 的 `_FETCHERS` 新增：

```python
from .tushare_fetcher import TushareFetcher
_FETCHERS = {
    "akshare": AkShareFetcher,
    "tushare": TushareFetcher,
}
```

#### 5.2 数据源 → 目标表的映射（核心路由）

新建 `backend/app/services/fetcher/registry.py`（或扩展 `__init__.py`），提供「源 → 行情表 ORM 模型 + fetcher」的统一映射：

```python
SOURCE_TABLE = {
    "akshare": RawPriceDaily,
    "tushare": RawPriceDailyTushare,
}

def resolve_source() -> str:
    """解析生效数据源：读 DB data_source_config；
    tushare_enabled=1 且 token 非空 → 'tushare'，否则 'akshare'。"""
```

> 该映射是「数据单独成表」与「避免重复拉取」的交汇点：拉取前用它定位目标表查本地、拉取后用它定位目标表 UPSERT。
> 开关关闭（`tushare_enabled=0`）时 `resolve_source()` 恒返回 `'akshare'`，原有免费逻辑零感知。

#### 5.3 `storage.upsert_bars` 参数化

当前 `upsert_bars(db, bars)` 硬编码写 `RawPriceDaily`。改为接收目标模型：

```python
def upsert_bars(db, bars: list[PriceBar], model=RawPriceDaily) -> int: ...
```

调用方按 `SOURCE_TABLE[source]` 传入对应模型。原 AkShare 调用点默认行为不变（向后兼容）。

### 6. source-aware 的 `ensure_price_data`

`backend/app/services/price_data.py` 的 `ensure_price_data` 改造为按开关路由（**这是实现「优先复用已存数据、避免重复拉取」的关键**）：

```python
def ensure_price_data(db, symbol, start, end) -> str | None:
    src = resolve_source()                   # 读开关：tushare_enabled=1 && token 非空 → 'tushare'，否则 'akshare'
    model = SOURCE_TABLE[src]                # 选对表
    fetcher = get_fetcher(src)               # 选对 fetcher
    # 后续 MIN/MAX/COUNT 查询、补缺区间、UPSERT 全部基于 model，逻辑不变
```

要点：
- **查本地**：`MIN/MAX/COUNT` 改查 `model`（Tushare 源查 `raw_price_daily_tushare`，AkShare 源查 `raw_price_daily`）。
- **补缺**：仅对缺失子区间调用 `fetcher.fetch_daily`，已有数据**完全跳过**（沿用现有 `FRONT_TOL` 节假日容忍逻辑）。
- **写回**：`upsert_bars(db, bars, model=model)`，UPSERT 保证边界重叠行幂等。
- **修复历史 gap**：现有 `ensure_price_data` 中 `get_fetcher()` 调用未传 source（默认 akshare，忽略 `settings.data_source`），本次一并修正为显式按源路由。

### 7. 回测引擎数据读取层适配（DCA + MA120）

回测计算引擎当前直接 `select(RawPriceDaily)` 读取行情。为支持「同一策略参数可分别跑 AkShare / Tushare 两份数据」，需将读取层参数化。

#### 7.1 计算引擎改造

- `app/services/compute/dca.py`、`app/services/compute/ma120.py` 读取行情的查询改为先 `resolve_source()` 决定读 `RawPriceDaily` 还是 `RawPriceDailyTushare`。
- `ensure_price_data(...)` 内部已自带开关路由，调用方无需传参。
- **开关关闭（默认）时整条链路读 `raw_price_daily`**，与升级前行为完全一致；开关开启且 Token 有效时才切到 Tushare 表。

#### 7.2 task_id 增加源标识（避免结果串台）

由于两份数据物理分表，**相同策略参数**跑不同源会得到不同结果，但 `task_id` 当前不含源 → 会写入同一条 summary，互相覆盖。

方案（**向后兼容，推荐**）：
- AkShare（默认源）**保持现有 task_id 不变**，不追加源段 → 旧缓存全部命中，平滑升级。
- Tushare 在 task_id 末尾追加 `_tushare`（如 `ma120_510880_..._batch_tushare`）→ 与 AkShare 结果隔离，互不覆盖。

> 即：`task_id` 规则在源为默认 `akshare` 时与 003/007 文档完全一致；仅当 `source != 'akshare'` 时追加 `_tushare`（或更通用的 `_{source}`）后缀。

#### 7.3 summary 表

`result_dca_summary` / `result_ma120_summary` **无需新增列**（源信息已编码进 `task_id`）；如需展示，可在 summary 增加可选 `data_source` 列（开放项，非必须）。

### 8. API 路由

新建 `backend/app/schemas/tushare.py` 与 `backend/app/api/tushare.py`，路由前缀 `/api/datasource`（语义更准，承载 Token + 源切换）。

#### 8.1 Schema（`schemas/tushare.py`）

```python
class TokenUpdate(BaseModel):
    token: str = Field(..., min_length=1, max_length=128)

class ToggleUpdate(BaseModel):
    enabled: bool

class DataSourceStatus(BaseModel):
    tushare_enabled: bool         # 开关状态（true=启用 Tushare，false=用 AkShare）
    active_source: str            # 解析后的生效源：'tushare' / 'akshare'（便于前端显示）
    tushare_token_masked: str     # 如 ••••abcd，未配置则为 ""
    tushare_configured: bool      # token 是否非空
```

#### 8.2 路由（`api/tushare.py`）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/datasource/status` | GET | 返回 `DataSourceStatus`（开关、掩码、生效源） |
| `/api/datasource/token` | PUT | 设置 / 更新 Tushare Token（明文入 DB） |
| `/api/datasource/token` | DELETE | 清空 Token |
| `/api/datasource/toggle` | PUT | 开关 Tushare；`enabled=true` 时**校验 Token 非空**，否则返回 `ApiResponse.error("启用 Tushare 前请先设置 Token")` |

**业务规则：**
- 所有接口返回统一 `ApiResponse`。
- Token 与开关均落库持久化，重启不丢；Token 写入后**不立即拉取**，仅持久化，实际拉取发生在回测或手动 fetch 时（避免无谓请求 / 触发限频）。
- 关闭开关（`enabled=false`）不清空 Token，仅让系统回退 AkShare 免费逻辑；后续重新启用无需重新填 Token。
- 生效源解析（`active_source`）= `tushare_enabled && tushare_configured ? 'tushare' : 'akshare'`，前端据此显示当前状态。

#### 8.3 手动拉取接口 `/api/data/fetch` 适配

`backend/app/api/data.py`：

- `fetcher = get_fetcher(settings.data_source)` → 改为 `src = resolve_source(); fetcher = get_fetcher(src)`（读开关状态）。
- `upsert_bars(db, bars)` → `upsert_bars(db, bars, model=SOURCE_TABLE[src])` 按开关写入对应表。
- 响应 `FetchResultData` 可新增 `source` 字段，标明本次写入哪张表。

### 9. 路由注册

`backend/app/main.py`：

```python
from .api import backtest, data, datasource, feedback, health, ma120, symbols
...
app.include_router(datasource.router, prefix="/api/datasource", tags=["datasource"])
```

### 验收标准（后端）

- [ ] `raw_price_daily_tushare` 与 `data_source_config` 两张表建成功（fresh 走 init/03，已部署走 migrations/004）
- [ ] 未配置 Token 时 `TushareFetcher.fetch_daily` 抛清晰中文错误
- [ ] 配置 Token 且开启开关后，手动 `POST /api/data/fetch` 能拉取真实标的并写入 `raw_price_daily_tushare`，`raw_price_daily` 不受影响
- [ ] 重复拉取相同区间不产生重复行（UPSERT 幂等）
- [ ] `ensure_price_data`：开关开启且区间已覆盖时**不发起请求**；仅缺前后段时补拉对应子区间
- [ ] **开关关闭时**：拉取 / 回测全部走 AkShare + `raw_price_daily`，即便已存 Token 也不被使用，行为与升级前完全一致
- [ ] Token 写入后**重启服务 / 容器**仍存在，开关状态同样保持
- [ ] GET `/api/datasource/status` 返回开关、Token 掩码与生效源
- [ ] PUT `/api/datasource/toggle` 开启但无 Token 时被拒绝；关闭时不要求 Token
- [ ] DCA / MA120 在开关开启下能完整跑通，结果写入带 `_tushare` 后缀的 task_id，与 AkShare 结果互不覆盖
- [ ] AkShare（开关关闭）链路行为完全不变，旧 task_id 缓存仍可命中
- [ ] Swagger UI (`/docs`) 可测试全部新接口

---

## Part B：前端

### 1. API 封装

`frontend/src/api/index.ts` 新增：

- `getDataSourceStatus()` → GET `/api/datasource/status`
- `updateTushareToken(body)` → PUT `/api/datasource/token`
- `clearTushareToken()` → DELETE `/api/datasource/token`
- `toggleTushare(enabled)` → PUT `/api/datasource/toggle`
- 对应 TypeScript 类型 `DataSourceStatus`（`tushare_enabled`、`active_source`、`tushare_token_masked`、`tushare_configured`）

### 2. 数据源设置组件（钥匙图标）

新建 `frontend/src/components/DataSourceWidget.vue`，结构对标 `FeedbackWidget.vue`（图标按钮 + Teleport 弹层）：

- **图标按钮**：36×36px 无边框（class 复用 `.feedback-btn` 同款样式），内含 20×20 钥匙 SVG（使用用户指定图标）：

```html
<svg class="datasource-icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg">
  <path d="M-664.554667 249.408" fill="currentColor"/>
  <path d="M-664.554667 249.408" fill="currentColor"/>
  <path d="M317.738667 590.122667c41.749333 0 78.08-36.330667 78.08-78.08s-36.330667-78.08-78.08-78.08-76.266667 36.330667-76.266667 78.08S275.989333 590.122667 317.738667 590.122667zM537.429333 433.962667 938.666667 433.962667l0 156.138667-78.08 0 0 154.304-154.304 0L706.282667 590.08l-168.832 0c-30.869333 90.794667-118.016 154.304-219.690667 154.304C188.821333 744.405333 85.333333 640.896 85.333333 512s103.488-232.405333 232.405333-232.405333c101.674667 0 188.821333 63.552 219.690667 154.304L537.429333 433.962667z" fill="currentColor"/>
</svg>
```

- 颜色用 `currentColor`（自适应明暗主题），hover 加深；开关开启时图标高亮（如 `--primary`），关闭时弱化（`--text-secondary`）以一眼区分状态。
- 点击弹出面板（Teleport to body，遮罩层 + 居中卡片），内容：
  - **Tushare 开关**：toggle switch（开关），关闭时面板下方提示「已使用免费数据源（AkShare）」，开启时提示「已使用 Tushare 数据源」
  - **Tushare Token**：密码型 input（`type="password"`），占位符显示掩码（如 `••••abcd`，来自 status 接口）；右侧「保存」「清除」按钮
  - **状态提示行**：
    - 未配置 Token + 尝试开启开关 → 红色提示「请先填写 Token 再开启」，开关保持关闭
    - 已配置 → 绿色「Token 已配置（••••abcd），重启服务后依然有效」
  - 底部说明：「Token 永久保存于本服务后端，在主动更新或清除前一直有效；关闭开关仅停用 Tushare，Token 原样保留，可随时重新启用；服务/容器重启后开关与 Token 均保持。」
  - 附 Tushare 注册链接 `https://tushare.pro/register`（新窗口打开）

**交互细节：**
- 打开面板时调用 `getDataSourceStatus()` 回填开关状态与掩码。
- 保存 Token → `updateTushareToken` → 成功后刷新 status。
- 切换开关 → 若开启但未配置 Token，前端先拦截提示，不发请求；否则 `toggleTushare(enabled)`，成功后更新本地状态。
- 关闭开关不清 Token，仅把面板提示切回「使用免费数据源」。
- 遮罩层点击关闭。

### 3. 导航栏集成

`frontend/src/App.vue`：

- `import DataSourceWidget from './components/DataSourceWidget.vue'`
- 放置在 `.nav-actions` 内、`<FeedbackWidget />` 与 `<button class="theme-switch">` 之间，即顺序为：`反馈 → 数据源(钥匙) → 主题切换`。

### 4. 样式要求

- 复用项目现有 CSS 变量（`--surface`、`--border`、`--text`、`--text-secondary`、`--primary`、`--input-bg`、`--hover-bg` 等），自动适配明暗主题。
- 面板宽度 ~420px，最大高度 80vh，内容区可滚动。
- 按钮主次区分：保存用 `--primary`，清除用低饱和文字按钮。

### 验收标准（前端）

- [ ] 导航栏出现**指定的钥匙 SVG 图标按钮**，位于反馈图标与主题切换之间
- [ ] 明暗主题切换后图标 / 面板样式正确
- [ ] 开关开启时图标高亮、关闭时弱化，状态一眼可辨
- [ ] 面板含 Tushare toggle switch，关闭时提示「使用免费数据源」，开启时提示「使用 Tushare」
- [ ] 面板可输入 Token 并保存，保存后显示掩码，提示「重启服务后依然有效」
- [ ] 清除 Token 后状态正确刷新
- [ ] 未配置 Token 时开启开关被前端拦截（双重大门：前端 + 后端）
- [ ] 关闭开关不清 Token，重新开启无需重填
- [ ] 切换开关后，重新发起回测使用对应数据源数据
- [ ] 遮罩层点击关闭面板

---

## 数据复用与隔离策略

| 维度 | 开关关闭（默认） | 开关开启（且 Token 有效） |
|------|------------------|---------------------------|
| 生效源 | `akshare` | `tushare` |
| 行情表 | `raw_price_daily`（原有，不动） | `raw_price_daily_tushare`（新建） |
| Fetcher | `AkShareFetcher` | `TushareFetcher` |
| 补数逻辑 | `ensure_price_data` → 读 akshare 表 | `ensure_price_data` → 读 tushare 表 |
| 复用原则 | 先查本地表，仅补缺失区间，UPSERT 幂等 | 同左，查 / 写均落在 tushare 表 |
| 回测 task_id | 现有规则不变 | 末尾追加 `_tushare` |
| Token | 保留不删，不使用 | 必须有效 |

> **关键原则**：两源数据**物理分表、逻辑同构**；任何拉取入口都先查对应本地表，已有数据直接复用，仅对缺失区间发起网络请求，从根本上避免重复拉取。
> 开关是「无侵入回退」开关：关闭即等价于本次扩展从未发生，原有免费链路零感知。

---

## 开放问题（后续迭代）

- [ ] **Token 加密存储**：当前明文存 DB（无鉴权场景可接受），后续可引入对称加密 / 接入鉴权后按用户隔离。
- [ ] **Tushare 限频治理**：超长区间分段拉取、请求间隔、失败重试与积分提示。
- [ ] **复权方式可选**：一期固定前复权（与 AkShare 对齐），后续可暴露 `adj`（qfq/hfq/none）作为拉取参数。
- [ ] **数据源质量比对视图**：同标的同区间 AkShare vs Tushare 行情差异对比页（利用分表天然支持）。
- [ ] **北交所 / 可转债等扩展标的**的 ts_code 映射与 asset 类型细化。
- [ ] summary 表增加 `data_source` 列，便于结果列表直观区分来源（非必须，task_id 已含信息）。
