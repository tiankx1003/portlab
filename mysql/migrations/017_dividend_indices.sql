-- 032 修正：补注册 4 个红利类指数（csindex 源有完整 PE 历史 + 股息率快照）
-- 已部署库升级用；fresh 安装由 init/12_valuation_v2.sql 提供（同源）。
-- 背景：512890 华泰柏瑞红利低波ETF 跟踪 H30269（中证红利低波动），非 930955（红利低波100）。
-- 实测（akshare 1.18.64）：4 者 csindex hist 均有「滚动市盈率」完整序列（2018 起），
-- csindex value 均有「股息率1」当日快照；PB 无数据源（硬伤二，仍灰）。
USE portlab;

INSERT INTO index_registry
    (index_code, name_cn, lg_name, source_type, supported, note, sort_order)
VALUES
    ('930955', '中证红利低波动100', NULL, 'csindex', 1, NULL, 13),
    ('H30269', '中证红利低波动',    NULL, 'csindex', 1, NULL, 14),
    ('000922', '中证红利',          NULL, 'csindex', 1, NULL, 15),
    ('000015', '上证红利',          NULL, 'csindex', 1, NULL, 16)
ON DUPLICATE KEY UPDATE name_cn = VALUES(name_cn), source_type = VALUES(source_type),
                        supported = VALUES(supported), sort_order = VALUES(sort_order);
