-- 007 MA120 策略回测：新增 calc_ma120_backtest 与 result_ma120_summary
-- 一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/01_schema.sql 包含这两张表。
USE portlab;

-- MA120 策略回测逐日计算结果
CREATE TABLE IF NOT EXISTS calc_ma120_backtest (
    task_id        VARCHAR(96)   NOT NULL COMMENT '回测任务 ID',
    trade_date     DATE          NOT NULL COMMENT '交易日',
    `signal`       VARCHAR(8)    NOT NULL DEFAULT 'hold' COMMENT '信号 buy/sell/hold',
    action_shares  DECIMAL(20,8) NOT NULL DEFAULT 0 COMMENT '当日操作份额(买入+ / 卖出-)',
    action_amount  DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '当日操作金额',
    holding_shares DECIMAL(20,8) NOT NULL DEFAULT 0 COMMENT '持仓份额',
    cash_balance   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '现金余额',
    cum_invested   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计投入本金',
    market_value   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '当日总市值(持仓+现金)',
    pnl            DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '盈亏',
    return_rate    DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '收益率(%)',
    ma_value       DECIMAL(14,4) NULL     COMMENT '当日均线值',
    price_vs_ma    DECIMAL(8,4)  NULL     COMMENT '价格相对 MA 偏离度(%)',
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, trade_date),
    KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MA120 策略回测逐日计算';

-- MA120 策略回测汇总指标
CREATE TABLE IF NOT EXISTS result_ma120_summary (
    task_id           VARCHAR(96)   NOT NULL COMMENT '回测任务 ID',
    symbol            VARCHAR(32)   NOT NULL COMMENT '标的代码',
    capital_mode      VARCHAR(16)   NOT NULL COMMENT '资金模式 fixed/recurring/hybrid',
    principal         DECIMAL(18,2) NULL     COMMENT '初始本金(fixed/hybrid)',
    monthly_amount    DECIMAL(18,2) NULL     COMMENT '月度投入(recurring/hybrid)',
    splits            INT           NOT NULL COMMENT '份数',
    ma_period         INT           NOT NULL COMMENT '均线周期',
    buy_threshold     DECIMAL(8,4)  NOT NULL COMMENT '起始买入阈值',
    step              DECIMAL(8,4)  NOT NULL COMMENT '加仓步长',
    sell_mode         VARCHAR(8)    NOT NULL COMMENT '卖出方式 batch/all/half',
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
    dividend_total    DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计分红',
    win_rate          DECIMAL(8,4)  NOT NULL DEFAULT 0 COMMENT '胜率(%)',
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id),
    KEY idx_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='MA120 策略回测汇总指标';
