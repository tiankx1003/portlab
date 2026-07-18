-- 010 更新日志（Release Notes）：release_notes 表
-- 由 MySQL 镜像在首次初始化（数据目录为空）时，于 03_tushare.sql 之后自动执行。
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

-- 预置最近迭代种子（幂等：title+released_at 唯一，重复执行不产生重复行）
INSERT INTO release_notes (title, type, detail, released_at, created_at) VALUES
('回测直达 / 更新日志 CLI / Tushare 限频治理', 'improvement', '?task= 直达已有回测结果；release_notes CLI 免 SQL 维护；Tushare 分段拉取+节流+重试', '2026-07-18', UTC_TIMESTAMP()),
('ETF 资金流向看板',           'feature',     '份额变动 + 北向资金(Tushare)，观察机构/国家队动向',  '2026-07-18', UTC_TIMESTAMP()),
('回撤买入策略看板',           'feature',     '拖动回撤阈值实时定义买点，金字塔分批买入、新高清仓',  '2026-07-18', UTC_TIMESTAMP()),
('更新日志 + GitHub 仓库入口', 'feature',     '导航栏铃铛展示最新 5 条变更；GitHub 外链图标',       '2026-07-18', UTC_TIMESTAMP()),
('首页改版为工具箱门户',       'feature',     '市场概览/最近回测/最近更新/Roadmap；品牌区可点击回首页', '2026-07-18', UTC_TIMESTAMP()),
('Tushare 数据源扩展',         'feature',     '右上角钥匙图标开关 Tushare 数据源；Token 持久化、行情独立成表、避免重复拉取', '2026-07-17', UTC_TIMESTAMP()),
('MA120 新增止盈步长参数',      'feature',     'batch 卖出方式下可配置止盈步长，灵活控制分批卖出节奏', '2026-07-16', UTC_TIMESTAMP()),
('问题反馈功能上线',           'feature',     '右上角反馈图标，支持 Markdown 提交，反馈保留 3 天',     '2026-07-16', UTC_TIMESTAMP()),
('图表图例提示与卡片交互优化',  'improvement', '图例新增提示图标；MA120 卡片/表单交互打磨',           '2026-07-16', UTC_TIMESTAMP()),
('红利 MA120 策略回测全链路',  'feature',     '新增 MA120 策略回测（计算引擎 + API + 前端）',        '2026-07-15', UTC_TIMESTAMP()),
('自定义品牌图标',             'improvement', 'favicon 与左上角 Logo 自定义',                       '2026-07-12', UTC_TIMESTAMP())
ON DUPLICATE KEY UPDATE title = VALUES(title);
