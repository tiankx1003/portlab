-- 009 Tushare 数据源：raw_price_daily_tushare 行情表 + data_source_config 单行配置
-- 由 MySQL 镜像在首次初始化（数据目录为空）时，于 02_feedback.sql 之后自动执行。
USE portlab;

-- Tushare 原始日线行情（与 raw_price_daily 物理隔离，便于两源分表比对）
CREATE TABLE IF NOT EXISTS raw_price_daily_tushare (
    symbol      VARCHAR(32)   NOT NULL COMMENT '标的代码',
    trade_date  DATE          NOT NULL COMMENT '交易日',
    open        DECIMAL(14,4) NOT NULL COMMENT '开盘价',
    close       DECIMAL(14,4) NOT NULL COMMENT '收盘价',
    high        DECIMAL(14,4) NOT NULL COMMENT '最高价',
    low         DECIMAL(14,4) NOT NULL COMMENT '最低价',
    volume      BIGINT        NULL     COMMENT '成交量(股)',
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date),
    KEY idx_symbol_date (symbol, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Tushare 原始日线行情';

-- 数据源单行配置（Tushare 开关 + Token），恒为 id=1
CREATE TABLE IF NOT EXISTS data_source_config (
    id              TINYINT       NOT NULL DEFAULT 1 COMMENT '恒为 1，单行配置',
    tushare_enabled TINYINT(1)    NOT NULL DEFAULT 0 COMMENT 'Tushare 开关 0=关闭(用AkShare免费) 1=启用(用Tushare)',
    tushare_token   VARCHAR(128)  NULL     COMMENT 'Tushare Pro Token(明文存储)',
    updated_at      TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据源单行配置';

-- 默认单行配置（幂等：已存在则不覆盖已有 Token / 开关）
INSERT INTO data_source_config (id, tushare_enabled, tushare_token)
VALUES (1, 0, NULL)
ON DUPLICATE KEY UPDATE id = id;
