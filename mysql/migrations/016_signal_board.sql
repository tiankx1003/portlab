-- 032 估值与信号看板：十年期国债 + 指数日线(含全收益) + 宏观指标 + 融资融券
-- 已部署库升级用；fresh 安装由 init/15_signal_board.sql 提供同四表。
USE portlab;

-- 十年期国债收益率日序列（中债 10 年；日频）
CREATE TABLE IF NOT EXISTS raw_bond_yield_daily (
    trade_date  DATE          NOT NULL COMMENT '交易日',
    yield_10y   DECIMAL(6,3)  NULL     COMMENT '十年期国债收益率(%)',
    source      VARCHAR(32)   NOT NULL DEFAULT 'bond_zh_us_rate' COMMENT '数据源',
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='十年期国债收益率日序列(032)';

-- 指数日线点位（价格 + 全收益共存；右轴/均值之锚用）
CREATE TABLE IF NOT EXISTS raw_index_daily (
    index_code  VARCHAR(16)   NOT NULL COMMENT '指数代码(含H全收益代码)',
    trade_date  DATE          NOT NULL COMMENT '交易日',
    close       DECIMAL(12,4) NULL     COMMENT '收盘点位',
    index_type  VARCHAR(16)   NOT NULL DEFAULT 'price' COMMENT 'price价格 / total_return全收益',
    source      VARCHAR(32)   NOT NULL DEFAULT 'akshare_daily' COMMENT 'akshare_daily / akshare_csindex',
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (index_code, trade_date),
    KEY idx_index_date (index_code, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指数日线点位(032)';

-- 宏观指标月/日序列（generic 表；Tushare）
CREATE TABLE IF NOT EXISTS raw_macro_indicator (
    indicator   VARCHAR(32)   NOT NULL COMMENT '指标键(sf_yoy/m1_yoy/m2_yoy/ppi_yoy/pmi)',
    ref_date    DATE          NOT NULL COMMENT '数据日期(月频取月初)',
    value       DECIMAL(12,4) NULL     COMMENT '指标值',
    source      VARCHAR(16)   NOT NULL DEFAULT 'tushare' COMMENT '数据源',
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (indicator, ref_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='宏观指标序列(032)';

-- 融资融券余额（交易所级汇总；Tushare 日频）
CREATE TABLE IF NOT EXISTS raw_margin_balance (
    trade_date  DATE          NOT NULL COMMENT '交易日',
    rzye        DECIMAL(16,2) NULL     COMMENT '融资余额(元)',
    rqye        DECIMAL(16,2) NULL     COMMENT '融券余额(元)',
    source      VARCHAR(16)   NOT NULL DEFAULT 'tushare' COMMENT '数据源',
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='融资融券余额(032)';
