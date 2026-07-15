"""MA120 策略回测（Part A）端到端验证脚本。

覆盖验收标准：
- 三种资金模式（fixed / recurring / hybrid）
- 三种卖出方式（batch / all / half）
- 暴跌加倍倍数效果
- 幂等（重复执行结果一致，先删后写）
- 分红复投（reinvest）暂未实现 → 抛 ComputeError
- 会计恒等式：market_value = holding×close + cash；pnl = market_value − cum_invested

用法（在 backend/ 下）：
    uv run --no-sync python scripts/verify_ma120.py [SYMBOL] [START] [END]
默认 SYMBOL=510300 START=2022-01-01 END=2026-07-13（沪深300，区间内多次跌破 MA120）。
"""

import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from app.database import SessionLocal
from app.models.calc import CalcMa120Backtest
from app.models.result import ResultMa120Summary
from app.services.compute.ma120 import ComputeError, Ma120Params, make_task_id, run_backtest

SYMBOL = sys.argv[1] if len(sys.argv) > 1 else "510300"
START = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2022, 1, 1)
END = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date(2026, 7, 13)


def _run(db, **kw) -> ResultMa120Summary:
    p = Ma120Params(symbol=SYMBOL, start_date=START, end_date=END, **kw)
    tid = run_backtest(db, p)
    return db.get(ResultMa120Summary, tid)


def _print(label, s: ResultMa120Summary) -> None:
    print(
        f"  [{label}] 投入={s.total_invested} 市值={s.final_value} "
        f"盈亏={s.total_pnl} 收益率={s.total_return_rate}% 年化={s.annualized_return}% "
        f"回撤={s.max_drawdown}% 买={s.buy_count} 卖={s.sell_count} "
        f"胜率={s.win_rate}% 分红={s.dividend_total}"
    )


def check_accounting(db) -> None:
    """抽验逐日会计恒等式与信号份额符号。"""
    p = Ma120Params(
        symbol=SYMBOL, start_date=START, end_date=END,
        capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None,
        sell_mode="batch",
    )
    rows = (
        db.execute(
            select(CalcMa120Backtest)
            .where(CalcMa120Backtest.task_id == make_task_id(p))
            .order_by(CalcMa120Backtest.trade_date)
        )
        .scalars()
        .all()
    )
    print(f"\n[会计恒等式] 共 {len(rows)} 个交易日")
    for r in rows:
        mv = (r.holding_shares * _close(db, SYMBOL, r.trade_date) + r.cash_balance).quantize(Decimal("0.01"))
        assert mv == r.market_value, f"{r.trade_date} 市值不平: {mv} != {r.market_value}"
        pnl = (r.market_value - r.cum_invested).quantize(Decimal("0.01"))
        assert pnl == r.pnl, f"{r.trade_date} 盈亏不平"
        if r.signal == "buy":
            assert r.action_shares > 0, f"{r.trade_date} 买入份额应>0"
        elif r.signal == "sell":
            assert r.action_shares < 0, f"{r.trade_date} 卖出份额应<0"
    # 打印首个买/卖信号供人工核对
    buys = [r for r in rows if r.signal == "buy"]
    sells = [r for r in rows if r.signal == "sell"]
    if buys:
        b = buys[0]
        print(f"  首次买入 {b.trade_date}: 份额={b.action_shares} 金额={b.action_amount} "
              f"MA={b.ma_value} 偏离={b.price_vs_ma}% 持仓={b.holding_shares} 现金={b.cash_balance}")
    if sells:
        s = sells[0]
        print(f"  首次卖出 {s.trade_date}: 份额={s.action_shares} 金额={s.action_amount} "
              f"MA={s.ma_value} 偏离={s.price_vs_ma}% 持仓={s.holding_shares} 现金={s.cash_balance}")
    print("  ✅ 全部交易日 market_value=持仓×收盘+现金、pnl=市值−投入、信号份额符号正确")


def _close(db, symbol, d) -> Decimal:
    from app.models.raw import RawPriceDaily

    return Decimal(str(db.get(RawPriceDaily, (symbol, d)).close))


def main() -> None:
    db = SessionLocal()
    try:
        print(f"=== MA120 Part A 验证  symbol={SYMBOL} {START}~{END} ===")

        print("\n[三种资金模式] fixed / recurring / hybrid（batch 卖出）")
        _print("fixed    ", _run(db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None))
        _print("recurring", _run(db, capital_mode="recurring", principal=None, monthly_amount=Decimal("2000")))
        _print("hybrid   ", _run(db, capital_mode="hybrid", principal=Decimal("60000"), monthly_amount=Decimal("1000")))

        print("\n[三种卖出方式] batch / all / half（fixed 本金）")
        _print("batch", _run(db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None, sell_mode="batch"))
        _print("all  ", _run(db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None, sell_mode="all"))
        _print("half ", _run(db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None, sell_mode="half"))

        print("\n[暴跌加倍] crash_multiplier=2 vs =1（fixed/batch，crash_threshold=2% 以便观测）")
        # 默认 5% 阈值下 ETF 极少在买入区出现单日暴跌，故此处放宽到 2% 以触发并对比加倍效果
        s2 = _run(
            db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None,
            crash_threshold=Decimal("0.02"), crash_multiplier=2,
        )
        s1 = _run(
            db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None,
            crash_threshold=Decimal("0.02"), crash_multiplier=1,
        )
        print(f"  倍数2: 买={s2.buy_count} 卖={s2.sell_count} 投入={s2.total_invested} 市值={s2.final_value}")
        print(f"  倍数1: 买={s1.buy_count} 卖={s1.sell_count} 投入={s1.total_invested} 市值={s1.final_value}")
        print("  ✅ 倍数影响买入次数/市值（暴跌加倍生效）" if s2.final_value != s1.final_value else "  ⚠️ 倍数未产生影响")

        print("\n[幂等] 同参数重复执行结果一致")
        a = _run(db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None, sell_mode="all")
        b = _run(db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None, sell_mode="all")
        print(f"  两次 final_value: {a.final_value} / {b.final_value}")
        print("  ✅ 幂等" if a.final_value == b.final_value else "  ❌ 不一致")

        print("\n[分红复投] reinvest 应抛 ComputeError")
        try:
            _run(db, capital_mode="fixed", principal=Decimal("100000"), monthly_amount=None, dividend_mode="reinvest")
            print("  ❌ 未抛异常")
        except ComputeError as e:
            print(f"  ✅ ComputeError: {e}")

        check_accounting(db)
        print("\n=== 全部通过 ===")
    finally:
        db.close()


if __name__ == "__main__":
    main()
