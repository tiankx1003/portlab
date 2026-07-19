-- 019 drawboard v2：新增 calc_drawboard_backtest 与 result_drawboard_summary
-- 一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/09_drawboard.sql 包含这两张表。
USE portlab;

-- 回撤买入策略回测逐日计算结果
CREATE TABLE IF NOT EXISTS calc_drawboard_backtest (
    task_id        VARCHAR(96)   NOT NULL COMMENT '回测任务 ID',
    trade_date     DATE          NOT NULL COMMENT '交易日',
    `signal`       VARCHAR(8)    NOT NULL DEFAULT 'hold' COMMENT '信号 buy/sell/hold',
    action_amount  DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '当日操作金额',
    holding        DECIMAL(20,8) NOT NULL DEFAULT 0 COMMENT '持仓份额',
    cum_invested   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计投入本金',
    cum_proceeds   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计套现(卖出回款)',
    market_value   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '当日市值(holding×price + cum_proceeds)',
    pnl            DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '盈亏 = mv − cum_invested',
    return_rate    DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '收益率(%)',
    drawdown       DECIMAL(8,4)  NOT NULL DEFAULT 0 COMMENT '当日滚动回撤(%)，负值',
    close          DECIMAL(14,4) NOT NULL DEFAULT 0 COMMENT '当日收盘(冗余，供 markPoint/tooltip 直读)',
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, trade_date),
    KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回撤买入策略回测逐日计算';

-- 回撤买入策略回测汇总指标
CREATE TABLE IF NOT EXISTS result_drawboard_summary (
    task_id           VARCHAR(96)   NOT NULL COMMENT '回测任务 ID',
    symbol            VARCHAR(32)   NOT NULL COMMENT '标的代码',
    sell_mode         VARCHAR(8)    NOT NULL COMMENT '卖出方式 none/new_high/partial',
    threshold         DECIMAL(8,4)  NOT NULL COMMENT '回撤阈值',
    step              DECIMAL(8,4)  NOT NULL COMMENT '加仓步长',
    buy_amount        DECIMAL(18,2) NOT NULL COMMENT '首笔金额',
    add_amount        DECIMAL(18,2) NOT NULL COMMENT '加仓金额',
    start_date        DATE          NOT NULL COMMENT '回测起始日',
    end_date          DATE          NOT NULL COMMENT '回测结束日',
    total_invested    DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计投入',
    final_value       DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '最终市值',
    total_pnl         DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计盈亏',
    total_return_rate DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '累计收益率(%)',
    annualized_return DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '年化收益率(%)(XIRR)',
    max_drawdown      DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '最大回撤(%)',
    buy_count         INT           NOT NULL DEFAULT 0 COMMENT '买入次数',
    sell_count        INT           NOT NULL DEFAULT 0 COMMENT '卖出次数',
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id),
    KEY idx_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='回撤买入策略回测汇总指标';
