-- 006 智能定投：calc_dca_backtest 新增扣款率与实际投入字段
-- 一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/01_schema.sql 包含这两列。
USE portlab;

ALTER TABLE calc_dca_backtest
    ADD COLUMN deduction_rate DECIMAL(5, 4) NULL COMMENT '扣款率(1.0=100%)，智能定投',
    ADD COLUMN actual_amount DECIMAL(16, 2) NULL COMMENT '当期实际投入金额，智能定投浮动';
