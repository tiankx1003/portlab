-- PortLab 初始 schema
-- 由 MySQL 镜像在首次初始化（数据目录为空）时自动执行。
-- 表命名约定：raw_* 原始 / calc_* 中间计算 / result_* 最终输出。

CREATE DATABASE IF NOT EXISTS portlab
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE portlab;

-- 原始日线行情数据（DataFetcher 写入）
CREATE TABLE IF NOT EXISTS raw_price_daily (
    symbol      VARCHAR(32)   NOT NULL COMMENT '标的代码',
    trade_date  DATE          NOT NULL COMMENT '交易日',
    open        DECIMAL(14,4) NOT NULL COMMENT '开盘价',
    close       DECIMAL(14,4) NOT NULL COMMENT '收盘价',
    high        DECIMAL(14,4) NOT NULL COMMENT '最高价',
    low         DECIMAL(14,4) NOT NULL COMMENT '最低价',
    volume      BIGINT        NULL     COMMENT '成交量',
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date),
    KEY idx_symbol_date (symbol, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='原始日线行情';

-- 定投回测逐日计算结果（003 实现写入，此处仅建表）
CREATE TABLE IF NOT EXISTS calc_dca_backtest (
    task_id       VARCHAR(64)   NOT NULL COMMENT '回测任务 ID',
    trade_date    DATE          NOT NULL COMMENT '交易日',
    is_invest_day TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否定投日',
    buy_shares    DECIMAL(20,8) NOT NULL DEFAULT 0 COMMENT '当日买入份额',
    cum_shares    DECIMAL(20,8) NOT NULL DEFAULT 0 COMMENT '累计份额',
    cum_cost      DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计投入成本',
    market_value  DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '当日市值',
    pnl           DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计盈亏',
    return_rate   DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '收益率(%)',
    updated_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, trade_date),
    KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定投回测逐日计算';

-- 定投回测汇总指标（003 实现写入，此处仅建表）
CREATE TABLE IF NOT EXISTS result_dca_summary (
    task_id           VARCHAR(64)   NOT NULL COMMENT '回测任务 ID',
    symbol            VARCHAR(32)   NOT NULL COMMENT '标的代码',
    frequency         VARCHAR(16)   NOT NULL COMMENT '定投频率 weekly/monthly',
    amount            DECIMAL(18,2) NOT NULL COMMENT '每期金额',
    invest_day        INT           NULL     COMMENT '投资日(周几0-6 / 月几1-28)',
    start_date        DATE          NOT NULL COMMENT '回测起始日',
    end_date          DATE          NOT NULL COMMENT '回测结束日',
    total_invested    DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计投入',
    final_value       DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '最终市值',
    total_pnl         DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计收益',
    total_return_rate DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '累计收益率(%)',
    annualized_return DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '年化收益率(%)',
    max_drawdown      DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '最大回撤(%)',
    invest_count      INT           NOT NULL DEFAULT 0 COMMENT '定投期数',
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id),
    KEY idx_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='定投回测汇总指标';
