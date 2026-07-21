-- 最近回测保存日志：记录每次「手动保存」（POST /{strategy}），按 saved_at 倒序供首页「最近回测」。
-- 仅手动保存写入；旧的「回测即落库」历史不在其中。每次保存刷新 saved_at（重新置顶）。
-- 由 MySQL 镜像在首次初始化（数据目录为空）时执行；已部署库见 migrations/013_recent_saves.sql。
USE portlab;

CREATE TABLE IF NOT EXISTS recent_saves (
    task_id  VARCHAR(96) CHARACTER SET ascii NOT NULL COMMENT '对应各策略 summary 表的 task_id',
    type     VARCHAR(16)  NOT NULL COMMENT 'dca/ma120/drawboard/grid',
    symbol   VARCHAR(32)  NOT NULL,
    saved_at DATETIME     NOT NULL COMMENT '保存时间（UTC，每次保存刷新）',
    PRIMARY KEY (task_id),
    KEY idx_saved (saved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='最近回测保存日志（首页最近记录用）';
