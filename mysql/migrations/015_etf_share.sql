-- 015 ETF 每日份额：raw_etf_share_daily（Tushare fund_share.fd_share）。
-- 一次性迁移脚本（已部署库升级用，手动执行）。fresh 安装已由 init/14_etf_share.sql 包含此表。
USE portlab;

-- ETF 每日总份额（万份，绝对值）；联动 PCF 时取连续两日算份额变动
CREATE TABLE IF NOT EXISTS raw_etf_share_daily (
    symbol      VARCHAR(32)   NOT NULL COMMENT 'ETF 代码',
    trade_date  DATE          NOT NULL COMMENT '交易日',
    fd_share    DECIMAL(20,4) NOT NULL COMMENT '基金总份额(万份)',
    source      VARCHAR(16)   NOT NULL DEFAULT 'tushare' COMMENT '数据源',
    updated_at  TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETF 每日总份额(Tushare fund_share)';
