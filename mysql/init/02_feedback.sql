-- 008 问题反馈：feedback 表
-- 由 MySQL 镜像在首次初始化（数据目录为空）时，于 01_schema.sql 之后自动执行。
USE portlab;

CREATE TABLE IF NOT EXISTS feedback (
    id          INT AUTO_INCREMENT,
    content     TEXT         NOT NULL COMMENT '反馈内容（Markdown）',
    nickname    VARCHAR(64)  NULL     COMMENT '可选昵称',
    created_at  DATETIME     NOT NULL COMMENT '创建时间（UTC）',
    expires_at  DATETIME     NOT NULL COMMENT '过期时间（created_at + 3 天）',
    is_deleted  TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '软删除',
    PRIMARY KEY (id),
    KEY idx_active (is_deleted, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='问题反馈';
