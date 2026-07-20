-- 020 网格交易策略回测持久化（已部署库升级用；fresh 安装由 init/10_grid_trading.sql 提供同两表）
USE portlab;

-- 网格交易策略回测逐日计算结果
CREATE TABLE IF NOT EXISTS calc_grid_backtest (
    task_id        VARCHAR(96)   NOT NULL COMMENT '回测任务 ID',
    trade_date     DATE          NOT NULL COMMENT '交易日',
    `signal`       VARCHAR(8)    NOT NULL DEFAULT 'hold' COMMENT '信号 buy/sell/hold',
    action_amount  DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '当日操作金额',
    holding_shares DECIMAL(20,8) NOT NULL DEFAULT 0 COMMENT '持仓份额',
    cash_balance   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '现金(cum_proceeds−cum_invested)',
    cum_invested   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计投入',
    cum_proceeds   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '累计卖出回款',
    market_value   DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '市值(holding×price+cum_proceeds)',
    pnl            DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '盈亏 = mv − cum_invested',
    return_rate    DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '收益率(%)',
    close          DECIMAL(14,4) NOT NULL DEFAULT 0 COMMENT '当日收盘(冗余，供 markPoint/tooltip 直读)',
    grid_index     INT           NOT NULL DEFAULT 0 COMMENT '当日所在网格格序号(可负)',
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, trade_date),
    KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='网格交易策略回测逐日计算';

-- 网格交易策略回测汇总指标
CREATE TABLE IF NOT EXISTS result_grid_summary (
    task_id           VARCHAR(96)   NOT NULL COMMENT '回测任务 ID',
    symbol            VARCHAR(32)   NOT NULL COMMENT '标的代码',
    center_price      DECIMAL(14,4) NOT NULL COMMENT '网格中枢价',
    step_pct          DECIMAL(8,4)  NOT NULL COMMENT '网格间距%',
    amount_per_level  DECIMAL(18,2) NOT NULL COMMENT '每格资金',
    n_levels_above    INT           NOT NULL COMMENT '上方格数',
    n_levels_below    INT           NOT NULL COMMENT '下方格数',
    bound_mode        VARCHAR(8)    NOT NULL COMMENT '突破处理 hold/stop/reset',
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
    grid_profit       DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '网格套利累计差价',
    cycle_count       INT           NOT NULL DEFAULT 0 COMMENT '完成买卖循环次数',
    created_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id),
    KEY idx_symbol (symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='网格交易策略回测汇总指标';
