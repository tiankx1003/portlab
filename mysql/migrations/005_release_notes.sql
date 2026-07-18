-- 010 更新日志（Release Notes）：release_notes 表
-- 一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/04_release_notes.sql 包含此表与种子数据。
USE portlab;

-- 更新日志（运营 / 开发手动维护，前端只读展示最新 5 条）
CREATE TABLE IF NOT EXISTS release_notes (
    id          INT AUTO_INCREMENT,
    title       VARCHAR(128)  NOT NULL COMMENT '标题（一句话摘要）',
    type        VARCHAR(16)   NOT NULL COMMENT '类型 feature/bugfix/improvement/notice',
    detail      TEXT          NULL     COMMENT '详情（Markdown，可选）',
    released_at DATE          NOT NULL COMMENT '发布日期（业务日期）',
    is_deleted  TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '软删除',
    created_at  DATETIME      NOT NULL COMMENT '记录创建时间（UTC）',
    PRIMARY KEY (id),
    UNIQUE KEY uk_title_date (title, released_at),
    KEY idx_released (is_deleted, released_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='更新日志';
