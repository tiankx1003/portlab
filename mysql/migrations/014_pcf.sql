-- 014 PCF（ETF 申购赎回清单）：成份券篮子宽表 + 基金级头部表。
-- 一次性迁移脚本（已部署库升级用，手动执行）。fresh 安装已由 init/13_pcf.sql 包含这两张表。
USE portlab;

-- 成份券篮子（每只成份股一行，多源统一宽表）
CREATE TABLE IF NOT EXISTS raw_pcf_basket (
    source        VARCHAR(16)   NOT NULL COMMENT '数据源 fsfund/huatai_pb/...',
    fund_code     VARCHAR(16)   NOT NULL COMMENT '基金代码',
    trading_day   DATE          NOT NULL COMMENT '交易日期',
    stock_code    VARCHAR(16)   NOT NULL COMMENT '成份股代码',
    fund_name     VARCHAR(64)   NULL COMMENT '基金简称(华泰等)',
    fund_codes    VARCHAR(64)   NULL COMMENT '操作代码(华泰)',
    fund_id       VARCHAR(32)   NULL COMMENT '基金/成份券基金ID',
    scid          VARCHAR(16)   NULL COMMENT '市场ID(华宝)',
    stock_short   VARCHAR(64)   NULL COMMENT '股票简称',
    gpsc          VARCHAR(16)   NULL COMMENT '股票市场',
    stock_codesrc VARCHAR(16)   NULL COMMENT '股票代码来源',
    `number`      DECIMAL(20,4) NULL COMMENT '数量(股)',
    tdje          DECIMAL(20,4) NULL COMMENT '替代/退订金额(语义随source)',
    sgtdje        DECIMAL(20,4) NULL COMMENT '申购替代/退订金额',
    shtdje        DECIMAL(20,4) NULL COMMENT '赎回替代/退订金额',
    yjbl          DECIMAL(12,6) NULL COMMENT '溢价/应交比例(%)',
    sg_yjbl       DECIMAL(12,6) NULL COMMENT '申购应交比例(华宝)',
    sh_zjbl       DECIMAL(12,6) NULL COMMENT '赎回资金比例(华宝)',
    discount_rate DECIMAL(12,6) NULL COMMENT '现金替代折价率(华泰)',
    premium_rate  DECIMAL(12,6) NULL COMMENT '现金替代溢价率(华泰)',
    tdbz          VARCHAR(16)   NULL COMMENT '替代/退订标志',
    buyorsell     VARCHAR(8)    NULL COMMENT '买卖标志(华泰)',
    mmbz          VARCHAR(8)    NULL COMMENT '买卖标志(华宝)',
    record_id     VARCHAR(32)   NULL COMMENT '记录ID(华宝)',
    reserved      VARCHAR(64)   NULL COMMENT '保留字段(华宝)',
    procflag      VARCHAR(16)   NULL COMMENT '处理标志(华宝)',
    updated_at    TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (source, fund_code, trading_day, stock_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETF PCF 成份券篮子(多源统一宽表)';

-- 基金级头部信息（每个 基金×日期 一行；华宝 fsfund 无头部 → 不入此表）
CREATE TABLE IF NOT EXISTS raw_pcf_day_info (
    source         VARCHAR(16)   NOT NULL COMMENT '数据源',
    fund_code      VARCHAR(16)   NOT NULL COMMENT '基金代码',
    trading_day    DATE          NOT NULL COMMENT '交易日期',
    fund_name      VARCHAR(64)   NULL COMMENT '基金简称',
    nav            DECIMAL(14,4) NULL COMMENT '基金净值',
    cash_component DECIMAL(20,4) NULL COMMENT '现金差额',
    estimate_cash_component DECIMAL(20,4) NULL COMMENT '预估现金差额',
    cash_dividend  DECIMAL(20,4) NULL COMMENT '现金红利',
    creation_redemption_unit BIGINT NULL COMMENT '最小申赎单位(份)',
    creation_limit   BIGINT NULL COMMENT '申购上限',
    redemption_limit BIGINT NULL COMMENT '赎回上限',
    max_cash_ratio DECIMAL(8,4)  NULL COMMENT '最大现金替代比例(%)',
    record_num     INT           NULL COMMENT '成份券数量',
    underlying_index VARCHAR(64) NULL COMMENT '标的指数',
    nav_per_cu     DECIMAL(14,4) NULL COMMENT '单位净值(对价)',
    pbuid          VARCHAR(32)   NULL COMMENT 'PBU编号',
    investor_account_id VARCHAR(32) NULL COMMENT '投资者账户ID',
    creation_redemption VARCHAR(16) NULL COMMENT '申赎标志',
    creation_redemption_mechanism VARCHAR(32) NULL COMMENT '申赎机制',
    publish        VARCHAR(16)   NULL COMMENT '发布标志',
    all_cash_flag_str VARCHAR(32) NULL COMMENT '全现金标志',
    updated_at     TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                  ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (source, fund_code, trading_day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='ETF PCF 基金级头部信息(华泰等;华宝无)';
