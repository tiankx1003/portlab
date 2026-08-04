#!/usr/bin/env python3
"""
华泰柏瑞基金 (huatai-pb.com) ETF 申购赎回清单 (PCF) 爬虫（CLI 薄壳）。

抓取 + 解析核心在 ``app.services.pcf_crawlers``；本脚本只负责参数解析、日期区间遍历、
CSV 落盘（成份券 + 可选基金级 dayInfo）与可选 ``--db`` 入库。用法不变。

用法（在 backend/ 下）：
    uv run --no-sync python scripts/pcf/crawl_huatai_pb_pcf.py \
        --codes 512890 --start 2026-07-01 --end 2026-07-30
    uv run --no-sync python scripts/pcf/crawl_huatai_pb_pcf.py \
        --codes-file codes.txt --start 2026-07-01 --end 2026-07-30 \
        --day-info exports/pcf_huatai_pb_dayinfo.csv --db
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import time
from contextlib import ExitStack
from datetime import datetime, timedelta

# 允许 import app 包（scripts/pcf/ 上两级 = backend/）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.services.pcf_crawlers import (  # noqa: E402
    HUATAI_BASKET_CN,
    HUATAI_BASKET_COLUMNS,
    HUATAI_DAYINFO_CN,
    HUATAI_DAYINFO_COLUMNS,
    fetch_pcf_day,
)

SOURCE = "huatai_pb"
COLUMNS = HUATAI_BASKET_COLUMNS
CN_HEADER = HUATAI_BASKET_CN
DAY_INFO_COLUMNS = HUATAI_DAYINFO_COLUMNS
DAY_INFO_CN_HEADER = HUATAI_DAYINFO_CN


def daterange(start: str, end: str):
    """生成 [start, end] 闭区间内每一天（YYYY-MM-DD），输入支持 YYYYMMDD 或 YYYY-MM-DD。"""
    fmt = "%Y-%m-%d" if "-" in start else "%Y%m%d"
    d0 = datetime.strptime(start, fmt).date()
    d1 = datetime.strptime(end, fmt).date()
    if d0 > d1:
        d0, d1 = d1, d0
    d = d0
    while d <= d1:
        yield d.strftime("%Y-%m-%d")
        d += timedelta(days=1)


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="抓取华泰柏瑞 ETF 申购赎回清单 (PCF) 并输出 CSV")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--codes", help="基金代码清单，逗号分隔，如 512890,510300")
    g.add_argument("--codes-file", help="基金代码文件，每行一个代码")
    p.add_argument("--start", required=True, help="起始日期 YYYYMMDD 或 YYYY-MM-DD")
    p.add_argument("--end", required=True, help="结束日期 YYYYMMDD 或 YYYY-MM-DD")
    p.add_argument("--out", default="exports/pcf_huatai_pb.csv", help="成份券篮子 CSV 路径")
    p.add_argument("--day-info", dest="day_info", help="可选：把基金级 dayInfo 写入该 CSV 路径")
    p.add_argument("--delay", type=float, default=0.3, help="每次请求间隔秒（防封），默认 0.3")
    p.add_argument("--retries", type=int, default=3, help="单请求重试次数，默认 3")
    p.add_argument("--cookie", help="可选 insert_cookie 值（当前非必需，留作后备）")
    p.add_argument("--cn", action="store_true", help="使用中文表头")
    p.add_argument("--append", action="store_true", help="追加模式（不写表头），便于分批合并")
    p.add_argument(
        "--db",
        action="store_true",
        help="同时写入 MySQL raw_pcf_basket(+raw_pcf_day_info)；延迟 import，不影响纯离线运行",
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
    mode = "a" if args.append else "w"

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    if args.day_info:
        os.makedirs(os.path.dirname(args.day_info) or ".", exist_ok=True)

    total_rows = 0
    total_di = 0
    empty_targets = 0
    step = 0
    basket_rows: list[dict] = []
    day_info_rows: list[dict] = []
    with ExitStack() as stack:
        fout = stack.enter_context(open(args.out, mode, encoding="utf-8-sig", newline=""))
        writer = csv.writer(fout)
        if write_header:
            writer.writerow(header)
        di_writer = None
        if args.day_info:
            fdio = stack.enter_context(
                open(args.day_info, mode, encoding="utf-8-sig", newline="")
            )
            di_writer = csv.writer(fdio)
            if write_header:
                di_header = (
                    [DAY_INFO_CN_HEADER[c] for c in DAY_INFO_COLUMNS] if args.cn
                    else DAY_INFO_COLUMNS
                )
                di_writer.writerow(di_header)
        for code in codes:
            for day in dates:
                step += 1
                try:
                    r = fetch_pcf_day(
                        SOURCE, code, day,
                        retries=args.retries, delay=args.delay, cookie=args.cookie,
                    )
                except Exception as e:  # noqa: BLE001 — 单条失败不中断整批
                    print(f"  [{step}/{total}] {code} {day}  ✗ {e}", file=sys.stderr)
                    time.sleep(args.delay)
                    continue
                rows = r["basket_rows"]
                di = r["day_info_row"]
                n = len(rows)
                if n == 0:
                    empty_targets += 1
                for row in rows:
                    if args.db:
                        basket_rows.append(row)
                    writer.writerow([row[c] for c in COLUMNS])
                total_rows += n
                if di:
                    if args.db:
                        day_info_rows.append(di)
                    if di_writer:
                        di_writer.writerow([di[c] for c in DAY_INFO_COLUMNS])
                        total_di += 1
                print(
                    f"  [{step}/{total}] {code} {day}  -> {n} 条"
                    + ("  (dayInfo ✓)" if di_writer and di else "")
                )
                time.sleep(args.delay)

    msg = (
        f"\n完成。共写入 {total_rows} 条成份券到 {args.out} "
        f"(其中 {empty_targets} 个 (基金×日期) 无数据)。"
    )
    if args.day_info:
        msg += f"\n基金级 dayInfo 共 {total_di} 行写入 {args.day_info}。"
    print(msg)
    if args.db:
        from app.database import SessionLocal
        from app.services.pcf_ingest import ingest_basket, ingest_day_info

        db = SessionLocal()
        try:
            if basket_rows:
                n, skip = ingest_basket(db, SOURCE, basket_rows)
                print(f"[DB] raw_pcf_basket 入库 {n} 行（跳过 {skip} 行缺主键）")
            if day_info_rows:
                n, skip = ingest_day_info(db, SOURCE, day_info_rows)
                print(f"[DB] raw_pcf_day_info 入库 {n} 行（跳过 {skip} 行缺主键）")
        finally:
            db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
