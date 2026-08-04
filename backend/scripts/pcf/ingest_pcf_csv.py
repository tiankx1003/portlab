#!/usr/bin/env python3
"""
把已生成的 PCF CSV 导入 MySQL（raw_pcf_basket / raw_pcf_day_info）。

与爬虫的 ``--db`` 共用同一套 ``app.services.pcf_ingest`` 入库逻辑，适用于：
- 历史 CSV（如手工积累的 exports/pcf_fsfund.csv）回填入库；
- 别处产生的 CSV（不经过爬虫实时抓取）入库。

用法（在 backend/ 下）：
    # 华宝成份券 CSV（英文表头）入库
    uv run --no-sync python scripts/pcf/ingest_pcf_csv.py \
        --source fsfund --basket exports/pcf_fsfund.csv

    # 华泰柏瑞成份券 + 头部 CSV（中文表头）入库
    uv run --no-sync python scripts/pcf/ingest_pcf_csv.py \
        --source huatai_pb --basket exports/pcf_huatai_pb.csv \
        --day-info exports/pcf_huatai_pb_dayinfo.csv --cn

说明：
- 默认按英文表头解析（爬虫默认输出）；加 ``--cn`` 按中文表头解析（反查爬虫 CN_HEADER）。
- 幂等：同一 (source, 基金, 交易日) 重跑会先删后写。
- fsfund 无头部信息，``--source fsfund --day-info`` 会静默 0 行。
"""

import argparse
import csv
import os
import sys

# 允许 import app 包（scripts/pcf/ 上两级 = backend/）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def _cn_reverse(source: str, kind: str) -> dict[str, str] | None:
    """返回 {中文表头: 英文列名} 反查表；该 source/kind 无中文表头则 None。"""
    from app.services.pcf_crawlers import (
        FSFUND_BASKET_CN,
        HUATAI_BASKET_CN,
        HUATAI_DAYINFO_CN,
    )

    if source == "fsfund" and kind == "basket":
        cn = FSFUND_BASKET_CN
    elif source == "huatai_pb" and kind == "basket":
        cn = HUATAI_BASKET_CN
    elif source == "huatai_pb" and kind == "day_info":
        cn = HUATAI_DAYINFO_CN
    else:
        return None
    return {v: k for k, v in cn.items()}


def load_rows(path: str, source: str, kind: str, cn: bool) -> list[dict]:
    """读 CSV 为 dict 列表（英文列名键）。--cn 时把中文表头反查成英文列名。"""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if cn:
        rev = _cn_reverse(source, kind)
        if rev is None:
            print(f"  ⚠ {source} 无 {kind} 中文表头映射，按英文解析", file=sys.stderr)
            return rows
        return [{rev.get(k, k): v for k, v in row.items()} for row in rows]
    return rows


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="把 PCF CSV 导入 MySQL")
    p.add_argument("--source", required=True, choices=["fsfund", "huatai_pb"], help="数据源")
    p.add_argument("--basket", help="成份券篮子 CSV 路径")
    p.add_argument("--day-info", dest="day_info", help="基金级头部 CSV 路径")
    p.add_argument("--cn", action="store_true", help="CSV 为中文表头（默认英文）")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not (args.basket or args.day_info):
        print("至少指定 --basket 或 --day-info 之一", file=sys.stderr)
        return 1

    from app.database import SessionLocal
    from app.services.pcf_ingest import ingest_basket, ingest_day_info

    db = SessionLocal()
    try:
        if args.basket:
            rows = load_rows(args.basket, args.source, "basket", args.cn)
            n, skip = ingest_basket(db, args.source, rows)
            print(f"[basket] {args.basket} -> raw_pcf_basket 入库 {n} 行（跳过 {skip} 行缺主键）")
        if args.day_info:
            rows = load_rows(args.day_info, args.source, "day_info", args.cn)
            n, skip = ingest_day_info(db, args.source, rows)
            print(f"[day_info] {args.day_info} -> raw_pcf_day_info 入库 {n} 行（跳过 {skip} 行）")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
