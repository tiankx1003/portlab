-- 013 最近回测保存日志：recent_saves 表
-- 一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/05_recent_saves.sql 包含此表。
USE portlab;

CREATE TABLE IF NOT EXISTS recent_saves (
    task_id  VARCHAR(96) CHARACTER SET ascii NOT NULL COMMENT '对应各策略 summary 表的 task_id',
    type     VARCHAR(16)  NOT NULL COMMENT 'dca/ma120/drawboard/grid',
    symbol   VARCHAR(32)  NOT NULL,
    saved_at DATETIME     NOT NULL COMMENT '保存时间（UTC，每次保存刷新）',
    PRIMARY KEY (task_id),
    KEY idx_saved (saved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='最近回测保存日志（首页最近记录用）';
