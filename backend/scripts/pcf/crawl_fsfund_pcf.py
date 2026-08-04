#!/usr/bin/env python3
"""
华宝基金 (fsfund) ETF 申购赎回清单 (PCF) 爬虫（CLI 薄壳）。

抓取 + MD5 签名 + 解析核心在 ``app.services.pcf_crawlers``；本脚本只负责参数解析、
日期区间遍历、CSV 落盘与可选 ``--db`` 入库。用法不变。

用法（在 backend/ 下）：
    uv run --no-sync python scripts/pcf/crawl_fsfund_pcf.py \
        --codes 562060,562090 --start 2026-06-15 --end 2026-06-22
    uv run --no-sync python scripts/pcf/crawl_fsfund_pcf.py \
        --codes-file codes.txt --start 20260615 --end 20260622 --db
"""

import argparse
import csv
import os
import sys
import time
from datetime import datetime, timedelta

# 允许 import app 包（scripts/pcf/ 上两级 = backend/）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.pcf_crawlers import (  # noqa: E402
    FSFUND_BASKET_CN,
    FSFUND_BASKET_COLUMNS,
    fetch_pcf_day,
)

SOURCE = "fsfund"
COLUMNS = FSFUND_BASKET_COLUMNS
CN_HEADER = FSFUND_BASKET_CN


def daterange(start: str, end: str):
    """生成 [start, end] 闭区间内每一天（YYYYMMDD），输入支持 YYYYMMDD 或 YYYY-MM-DD。"""
    fmt = "%Y-%m-%d" if "-" in start else "%Y%m%d"
    d0 = datetime.strptime(start, fmt).date()
    d1 = datetime.strptime(end, fmt).date()
    if d0 > d1:
        d0, d1 = d1, d0
    d = d0
    while d <= d1:
        yield d.strftime("%Y%m%d")
        d += timedelta(days=1)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="抓取 fsfund ETF 申购赎回清单并输出 CSV")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--codes", help="基金代码清单，逗号分隔，如 562060,562090")
    g.add_argument("--codes-file", help="基金代码文件，每行一个代码")
    p.add_argument("--start", required=True, help="起始日期 YYYYMMDD 或 YYYY-MM-DD")
    p.add_argument("--end", required=True, help="结束日期 YYYYMMDD 或 YYYY-MM-DD")
    p.add_argument("--out", default="exports/pcf_fsfund.csv", help="输出 CSV 路径")
    p.add_argument("--delay", type=float, default=0.3, help="每次请求间隔秒（防封），默认 0.3")
    p.add_argument("--retries", type=int, default=3, help="单请求重试次数，默认 3")
    p.add_argument("--cn", action="store_true", help="使用中文表头")
    p.add_argument("--append", action="store_true", help="追加模式（不写表头），便于分批合并")
    p.add_argument(
        "--db",
        action="store_true",
        help="同时写入 MySQL raw_pcf_basket（延迟 import，不带此开关仍是纯离线脚本）",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    if args.codes:
        codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    else:
        with open(args.codes_file, encoding="utf-8") as f:
            codes = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    codes = list(dict.fromkeys(codes))  # 去重保序

    dates = list(daterange(args.start, args.end))
    total = len(codes) * len(dates)
    if total == 0:
        print("无可抓取的 (基金×日期) 组合，退出。", file=sys.stderr)
        return 1

    print(f"开始抓取：{len(codes)} 只基金 × {len(dates)} 天 = {total} 个请求")
    header = [CN_HEADER[c] for c in COLUMNS] if args.cn else COLUMNS
    write_header = not args.append

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    total_rows = 0
    empty_targets = 0
    basket_rows: list[dict] = []
    with open(args.out, "a" if args.append else "w", encoding="utf-8-sig", newline="") as fout:
        writer = csv.writer(fout)
        if write_header:
            writer.writerow(header)
        step = 0
        for code in codes:
            for day in dates:
                step += 1
                try:
                    r = fetch_pcf_day(SOURCE, code, day, retries=args.retries, delay=args.delay)
                except Exception as e:  # noqa: BLE001 — 单条失败不中断整批
                    print(f"  [{step}/{total}] {code} {day}  ✗ {e}", file=sys.stderr)
                    time.sleep(args.delay)
                    continue
                rows = r["basket_rows"]
                n = len(rows)
                if n == 0:
                    empty_targets += 1
                for row in rows:
                    if args.db:
                        basket_rows.append(row)
                    writer.writerow([row[c] for c in COLUMNS])
                total_rows += n
                print(f"  [{step}/{total}] {code} {day}  -> {n} 条")
                time.sleep(args.delay)

    print(
        f"\n完成。共写入 {total_rows} 条到 {args.out} "
        f"(其中 {empty_targets} 个 (基金×日期) 无数据)。"
    )
    if args.db and basket_rows:
        from app.database import SessionLocal
        from app.services.pcf_ingest import ingest_basket

        db = SessionLocal()
        try:
            n, skip = ingest_basket(db, SOURCE, basket_rows)
        finally:
            db.close()
        print(f"[DB] raw_pcf_basket 入库 {n} 行（跳过 {skip} 行缺主键）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
