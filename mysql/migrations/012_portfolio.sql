-- 022 组合回测持久化（已部署库升级用；fresh 安装由 init/11_portfolio.sql 提供同两表）
USE portlab;

-- 组合回测逐日净值
CREATE TABLE IF NOT EXISTS calc_portfolio_nav (
    task_id    VARCHAR(96)  NOT NULL COMMENT '回测任务 ID',
    trade_date DATE         NOT NULL COMMENT '交易日',
    nav        DECIMAL(12,6) NOT NULL DEFAULT 1 COMMENT '归一化净值(起点=1)',
    drawdown   DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT '当日回撤(%)，负值',
    updated_at TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, trade_date),
    KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组合回测逐日净值';

-- 组合回测汇总指标
CREATE TABLE IF NOT EXISTS result_portfolio_summary (
    task_id            VARCHAR(96)  NOT NULL COMMENT '回测任务 ID',
    symbols            VARCHAR(255) NOT NULL COMMENT '标的列表(逗号分隔)',
    mode               VARCHAR(8)   NOT NULL COMMENT '模式 fixed/frontier',
    weights            VARCHAR(255) NOT NULL COMMENT '权重(逗号分隔)',
    rebalance          VARCHAR(8)   NOT NULL COMMENT '再平衡 monthly/quarterly/none',
    start_date         DATE         NOT NULL COMMENT '回测起始日',
    end_date           DATE         NOT NULL COMMENT '回测结束日',
    annual_return      DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '年化收益(%)',
    annual_volatility  DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '年化波动(%)',
    sharpe             DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '夏普比率',
    max_drawdown       DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '最大回撤(%)',
    total_return       DECIMAL(12,4) NOT NULL DEFAULT 0 COMMENT '累计收益(%)',
    rf                 DECIMAL(8,4) NOT NULL DEFAULT 0 COMMENT '无风险利率',
    allow_short        INT          NOT NULL DEFAULT 0 COMMENT '是否允许做空',
    created_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at         TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id),
    KEY idx_symbols (symbols)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组合回测汇总指标';
