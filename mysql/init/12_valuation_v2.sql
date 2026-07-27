-- 024 估值看板 v2：指数估值日序列 + 指数注册表
-- fresh 安装由本文件建表；已部署库走 migrations/013_valuation_v2.sql（同两表）。
USE portlab;

-- 指数估值日序列（PE/PB/股息率；lg + csindex 双源统一存此表）
CREATE TABLE IF NOT EXISTS raw_index_valuation_daily (
    index_code     VARCHAR(16)    NOT NULL COMMENT '指数代码',
    trade_date     DATE           NOT NULL COMMENT '交易日',
    pe_ttm         DECIMAL(12,4)  NULL     COMMENT '滚动市盈率(核心，lg/csindex 统一)',
    pb             DECIMAL(12,4)  NULL     COMMENT '市净率(仅 lg 源)',
    dividend_yield DECIMAL(8,4)   NULL     COMMENT '股息率(%)(仅 csindex 快照)',
    source         VARCHAR(16)    NOT NULL COMMENT 'lg / csindex',
    updated_at     TIMESTAMP      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (index_code, trade_date),
    KEY idx_index_date (index_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数估值日序列(024)';

-- 指数注册表（替代 016 硬编码字典；12 个指数，7 可用 / 5 灰显）
CREATE TABLE IF NOT EXISTS index_registry (
    index_code  VARCHAR(16)  NOT NULL COMMENT '指数代码(科创板指去重用别名 KCBZ)',
    name_cn     VARCHAR(32)  NOT NULL COMMENT '中文显示名',
    lg_name     VARCHAR(32)  NULL     COMMENT 'lg 查询用中文名(仅 source_type=lg)',
    source_type VARCHAR(16)  NOT NULL COMMENT 'lg / csindex / none',
    supported   TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '本期是否可用',
    note        VARCHAR(160) NULL     COMMENT '说明(不支持原因等)',
    sort_order  INT          NOT NULL DEFAULT 0 COMMENT '下拉排序',
    PRIMARY KEY (index_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数注册表(024)';

-- 预置 12 行：7 supported=1（5 lg + 中证2000/科创50 csindex），5 supported=0
INSERT INTO index_registry
    (index_code, name_cn, lg_name, source_type, supported, note, sort_order)
VALUES
    ('000016','上证50',   '上证50',   'lg',      1, NULL, 1),
    ('000300','沪深300',  '沪深300',  'lg',      1, NULL, 2),
    ('000905','中证500',  '中证500',  'lg',      1, NULL, 3),
    ('000906','中证800',  '中证800',  'lg',      1, NULL, 4),
    ('000852','中证1000', '中证1000', 'lg',      1, NULL, 5),
    ('932000','中证2000', NULL,       'csindex', 1, NULL, 6),
    ('000688','科创50',   NULL,       'csindex', 1, NULL, 7),
    ('KCBZ',  '科创板指', NULL,       'none',    0, '与科创50(000688)成分相同，不重复列出，请选「科创50」', 8),
    ('000001','上证指数', NULL,       'none',    0, 'akshare 无该指数的指数级 PE/PB（lg 无该宽基，csindex 不覆盖上交所发布指数）', 9),
    ('399001','深证成指', NULL,       'none',    0, 'akshare 无该指数的指数级 PE/PB（csindex 不覆盖深交所发布指数）', 10),
    ('399006','创业板指', NULL,       'none',    0, 'akshare 无该指数的指数级 PE/PB（lg 仅有创业板50，csindex 不覆盖国证/深交所指数）', 11),
    ('886037','微盘',     NULL,       'none',    0, 'akshare 双源皆无微盘股指数级 PE/PB 数据', 12)
ON DUPLICATE KEY UPDATE name_cn = VALUES(name_cn);
