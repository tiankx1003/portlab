-- 018 事件冲击产业链看板：event / theme / theme_stock / event_stock / llm_config
-- 一次性迁移脚本（已部署库升级用）。fresh 安装已由 init/08_event_dashboard.sql 包含。
-- 两份文件内容相同；本文件用于线上库手动升级（幂等，可重复执行）。
USE portlab;

-- 事件（一次真实冲击，如「茉莉花产地受灾」）
CREATE TABLE IF NOT EXISTS event (
    id          INT          NOT NULL AUTO_INCREMENT COMMENT '事件 ID',
    name        VARCHAR(64)  NOT NULL COMMENT '事件名',
    event_date  DATE         NOT NULL COMMENT '事件发生日',
    description TEXT         NULL     COMMENT '事件描述(供 LLM 匹配)',
    theme_id    INT          NULL     COMMENT '关联的主题模板 FK theme',
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_event_date (event_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件(事件冲击产业链看板)';

-- 主题模板（可复用的标的池）
CREATE TABLE IF NOT EXISTS theme (
    id         INT          NOT NULL AUTO_INCREMENT COMMENT '主题 ID',
    name       VARCHAR(64)  NOT NULL COMMENT '主题名',
    keywords   TEXT         NULL     COMMENT '关键词(逗号分隔,供智能匹配召回)',
    is_builtin TINYINT(1)   NOT NULL DEFAULT 0 COMMENT '是否系统预置',
    created_at DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    KEY idx_builtin (is_builtin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='主题模板(可复用标的池)';

-- 主题标的池（含产业链分组）
CREATE TABLE IF NOT EXISTS theme_stock (
    id         INT           NOT NULL AUTO_INCREMENT COMMENT '主键',
    theme_id   INT           NOT NULL COMMENT 'FK theme',
    symbol     VARCHAR(32)   NOT NULL COMMENT '标的代码',
    chain_role VARCHAR(16)   NOT NULL COMMENT '产业链角色 upstream/midstream/downstream',
    weight     DECIMAL(5,2)  NOT NULL DEFAULT 1.00 COMMENT '环节内权重',
    PRIMARY KEY (id),
    UNIQUE KEY uk_theme_stock_symbol (theme_id, symbol),
    KEY idx_theme_symbol (theme_id, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='主题标的池(含产业链分组)';

-- 事件实例标的池（从主题复制可改）
CREATE TABLE IF NOT EXISTS event_stock (
    id         INT           NOT NULL AUTO_INCREMENT COMMENT '主键',
    event_id   INT           NOT NULL COMMENT 'FK event',
    symbol     VARCHAR(32)   NOT NULL COMMENT '标的代码',
    chain_role VARCHAR(16)   NOT NULL COMMENT '产业链角色 upstream/midstream/downstream',
    PRIMARY KEY (id),
    UNIQUE KEY uk_event_stock_symbol (event_id, symbol),
    KEY idx_event_symbol (event_id, symbol)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='事件实例标的池(从主题复制可改)';

-- 大模型连接配置（单行，恒 id=1）
CREATE TABLE IF NOT EXISTS llm_config (
    id         TINYINT       NOT NULL DEFAULT 1 COMMENT '恒为 1，单行配置',
    api_base   VARCHAR(255)  NULL     COMMENT 'LLM API 地址',
    api_key    VARCHAR(255)  NULL     COMMENT 'API Key(明文存储)',
    model      VARCHAR(64)   NULL     COMMENT '模型名',
    enabled    TINYINT(1)    NOT NULL DEFAULT 0 COMMENT '是否启用 LLM 智能匹配',
    updated_at TIMESTAMP     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='大模型连接配置(单行)';

-- 默认单行配置（幂等：已存在则不覆盖）
INSERT INTO llm_config (id, api_base, api_key, model, enabled)
VALUES (1, NULL, NULL, NULL, 0)
ON DUPLICATE KEY UPDATE id = id;

-- 预置内置主题模板（id 固定 1~3，便于 theme_stock 引用；幂等）
INSERT IGNORE INTO theme (id, name, keywords, is_builtin) VALUES
    (1, '新茶饮产业链', '新茶饮,奶茶,花茶,茶饮,茉莉花,茶叶', 1),
    (2, '香料产业链',   '香料,香精,食用香精,提取,茉莉,花香', 1),
    (3, '农业种植',     '农业,种植,种子,农产品,花卉,经济作物', 1);

-- 预置成分股（starter 样例，真实可经概念板块/智能匹配补全；幂等）
-- 注：仅为可运行样例，可在前端「标的池表格」自由增删改链角色。
INSERT IGNORE INTO theme_stock (theme_id, symbol, chain_role, weight) VALUES
    -- 新茶饮产业链（id=1）
    (1, '600598', 'upstream',   1.00),  -- 北大荒（种植/原料）
    (1, '000998', 'upstream',   0.80),  -- 隆平高科（种业）
    (1, '002568', 'midstream',  1.00),  -- 百润股份（香精香料/预调酒）
    (1, '600872', 'midstream',  0.70),  -- 中炬高新（调味/食品）
    (1, '603288', 'downstream', 1.00),  -- 海天味业（食品龙头）
    (1, '603027', 'downstream', 0.60),  -- 千禾味业（调味）
    -- 香料产业链（id=2）
    (2, '600251', 'upstream',   1.00),  -- 冠农股份（种植/加工）
    (2, '600598', 'upstream',   0.70),  -- 北大荒
    (2, '002568', 'midstream',  1.00),  -- 百润股份（食用香精）
    (2, '600872', 'midstream',  0.70),  -- 中炬高新
    (2, '603288', 'downstream', 0.80),  -- 海天味业（应用端）
    (2, '600887', 'downstream', 0.50),  -- 伊利股份（乳饮应用）
    -- 农业种植（id=3）
    (3, '000998', 'upstream',   1.00),  -- 隆平高科
    (3, '600598', 'upstream',   1.00),  -- 北大荒
    (3, '600108', 'upstream',   0.70),  -- 亚盛集团
    (3, '000061', 'midstream',  1.00),  -- 农产品（批发市场）
    (3, '600887', 'downstream', 0.80),  -- 伊利股份
    (3, '603288', 'downstream', 0.60);  -- 海天味业
