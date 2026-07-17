"""红利 MA120 策略回测计算引擎。

策略（参考 docs/refer/收割机修订版_红利ETF_MA120策略.md）：
价格跌破 MA120 × buy_threshold 时金字塔分批买入（每跌 step 加 1 份，暴跌加倍），
站回 MA120 上方后按卖出方式（分批 / 全部 / 半仓）兑现，不止损。

支持三种资金模式：
- ``fixed``：初始本金一笔到位，分成 ``splits`` 份逐份使用。
- ``recurring``：无初始本金，每月月初资金入池，从池中取用。
- ``hybrid``：初始本金 + 每月追加。

核心会计恒等式（逐日）：
    cash_balance = (cum_invested − 已部署本金) + 卖出回款 + 分红
    market_value = holding_shares × close + cash_balance
    pnl          = market_value − cum_invested   （cum_invested 为累计投入本金）

每份买入金额 ``unit_amount``：fixed→principal/splits；recurring→monthly_amount/splits；
hybrid→principal/splits（月度追加作为现金直接入资金池）。

MA 计算与行情加载复用 ``compute.common``；金额/份额用 Decimal，年化与回撤转 float。
task_id 由全部参数确定性生成，重复执行幂等（先删后写）。
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import delete
from sqlalchemy.orm import Session

from ...models.calc import CalcMa120Backtest
from ...models.result import ResultMa120Summary
from .common import annualized_return, compute_ma, load_prices, max_drawdown

_Q8 = Decimal("0.00000001")  # 份额 8 位
_Q4 = Decimal("0.0001")  # 百分比 / 偏离度 4 位
_Q2 = Decimal("0.01")  # 金额 2 位


class ComputeError(Exception):
    """回测计算业务异常。"""


@dataclass(frozen=True)
class Ma120Params:
    symbol: str
    start_date: date
    end_date: date
    capital_mode: str  # fixed/recurring/hybrid
    principal: Decimal | None
    monthly_amount: Decimal | None
    splits: int = 10
    ma_period: int = 120
    buy_threshold: Decimal = Decimal("0.985")
    step: Decimal = Decimal("0.01")
    crash_threshold: Decimal = Decimal("0.05")
    crash_multiplier: int = 2
    sell_mode: str = "batch"  # batch/all/half
    batch_sell_step: Decimal = Decimal("0.02")  # batch: 站回 MA 后再涨此步长触发卖出
    dividend_mode: str = "cash"  # cash（reinvest 暂未实现）


def make_task_id(p: Ma120Params) -> str:
    """由全部参数确定性生成 task_id，保证幂等。

    规格文档给出基础格式，此处额外追加 crash_threshold / crash_multiplier / dividend_mode，
    使所有影响结果的参数都进入 task_id（满足"全部参数确定性生成"）。
    """
    principal = p.principal if p.principal is not None else "0"
    monthly = p.monthly_amount if p.monthly_amount is not None else "0"
    return (
        f"ma120_{p.symbol}_{p.start_date:%Y%m%d}_{p.end_date:%Y%m%d}"
        f"_{p.capital_mode}_{principal}_{monthly}_{p.splits}"
        f"_{p.ma_period}_{p.buy_threshold}_{p.step}_{p.sell_mode}"
        f"_{p.crash_threshold}_{p.crash_multiplier}_{p.dividend_mode}_{p.batch_sell_step}"
    )


def lookback_days(ma_period: int) -> int:
    """MA 计算需回溯足够历史；返回额外向前加载的日历天数（与 DCA 智能定投一致）。"""
    return ma_period * 2


def run_backtest(db: Session, p: Ma120Params) -> str:
    """执行回测，逐日结果写入 calc_ma120_backtest，汇总写入 result_ma120_summary。返回 task_id。"""
    if p.dividend_mode == "reinvest":
        raise ComputeError("分红复投（reinvest）暂未实现，一期仅支持 cash")
    if p.capital_mode not in ("fixed", "recurring", "hybrid"):
        raise ComputeError(f"不支持的资金模式: {p.capital_mode}")
    if p.sell_mode not in ("batch", "all", "half"):
        raise ComputeError(f"不支持的卖出方式: {p.sell_mode}")
    if p.splits < 1:
        raise ComputeError("份数 splits 必须 ≥ 1")
    if not (Decimal(0) < p.batch_sell_step < Decimal(1)):
        raise ComputeError("止盈步长 batch_sell_step 必须 > 0 且 < 1")

    task_id = make_task_id(p)
    load_start = p.start_date - timedelta(days=lookback_days(p.ma_period))

    all_days = load_prices(db, p.symbol, load_start, p.end_date)
    if not any(d >= p.start_date for d, _ in all_days):
        raise ComputeError(
            f"标的 {p.symbol} 在 {p.start_date}~{p.end_date} 无行情数据，请先拉取数据"
        )

    ma_series = compute_ma(all_days, p.ma_period)
    calc_rows, market_values, cashflows, counts = _daily_calc(task_id, p, all_days, ma_series)

    dates = [r.trade_date for r in calc_rows]
    summary = _build_summary(task_id, p, dates, market_values, cashflows, counts)

    _write_results(db, task_id, calc_rows, summary)
    return task_id


# --------------------------- 内部实现 ---------------------------


def _unit_amount(p: Ma120Params) -> Decimal:
    """每次"1 份"买入的金额。"""
    if p.capital_mode == "recurring":
        return ((p.monthly_amount or Decimal(0)) / Decimal(p.splits)).quantize(_Q2)
    return ((p.principal or Decimal(0)) / Decimal(p.splits)).quantize(_Q2)


def _daily_calc(task_id, p, all_days, ma_series):
    unit_amount = _unit_amount(p)
    step_down = Decimal(1) - p.step
    batch_up = Decimal(1) + p.batch_sell_step

    holding = Decimal(0)
    deployed_cost = Decimal(0)  # 当前持仓的成本基础
    cash = Decimal(0)
    cum_invested = Decimal(0)  # 累计投入本金

    last_buy_price: Decimal | None = None  # 本轮最近一次买入价；为 None 表示待首次买入
    prev_above_ma = False
    # batch 卖出状态
    last_sell_price: Decimal | None = None
    batch_sells_done = 0  # 本轮已分批卖出次数（reset on 站回 MA）

    buy_count = 0
    sell_count = 0
    profitable_sells = 0
    dividend_total = Decimal(0)  # cash 模式无分红数据源，恒为 0

    calc_rows: list[CalcMa120Backtest] = []
    market_values: list[float] = []
    cashflows: list[tuple[date, float]] = []

    prev_ym = None
    first_day = True
    prev_close: Decimal | None = None

    for d, close in all_days:
        ma = ma_series.get(d)
        above_ma = ma is not None and ma > 0 and close > ma

        # 预热期：仅维护状态（prev_close / prev_above_ma），不交易、不入账、不写行
        if d < p.start_date:
            prev_close = close
            prev_above_ma = above_ma
            continue

        # ---- 资金到账 ----
        ym = (d.year, d.month)
        if ym != prev_ym and p.capital_mode in ("recurring", "hybrid"):
            amt = p.monthly_amount or Decimal(0)
            cum_invested += amt
            cash += amt
            cashflows.append((d, -float(amt)))
        if first_day and p.capital_mode in ("fixed", "hybrid"):
            amt = p.principal or Decimal(0)
            cum_invested += amt
            cash += amt
            cashflows.append((d, -float(amt)))
        first_day = False
        prev_ym = ym

        signal = "hold"
        action_shares = Decimal(0)
        action_amount = Decimal(0)

        if ma is not None and ma > 0:
            buy_line = ma * p.buy_threshold
            # 暴跌判定：单日跌幅 ≥ crash_threshold
            crash_day = (
                prev_close is not None
                and prev_close > 0
                and (prev_close - close) / prev_close >= p.crash_threshold
            )

            if close < buy_line:
                # ---------------- 买入区 ----------------
                # 首次买入 或 较上次买入价再跌 step → 基础 1 份
                ladder_hit = last_buy_price is None or close <= last_buy_price * step_down
                n_units = 1 if ladder_hit else 0
                if crash_day:
                    # 暴跌独立触发（捕捉急跌）并将份数加倍
                    n_units = max(n_units, 1) * p.crash_multiplier
                if n_units > 0:
                    want = (Decimal(n_units) * unit_amount).quantize(_Q2)
                    buy_amount = min(want, cash)  # 资金池不足时有多少买多少
                    if buy_amount > 0:
                        shares = (buy_amount / close).quantize(_Q8)
                        holding += shares
                        deployed_cost += buy_amount
                        cash -= buy_amount
                        action_shares = shares
                        action_amount = buy_amount
                        last_buy_price = close
                        signal = "buy"
                        buy_count += 1
            elif above_ma:
                # ---------------- 卖出区：站回 MA 上方 ----------------
                last_buy_price = None  # 结束本轮买入阶梯
                just_crossed_up = not prev_above_ma
                if holding > 0:
                    sell_shares = Decimal(0)
                    if p.sell_mode == "all":
                        if just_crossed_up:
                            sell_shares = holding  # 当日全部清仓
                    elif p.sell_mode == "half":
                        if just_crossed_up:
                            sell_shares = holding * Decimal("0.5")  # 卖半留底仓
                    else:  # batch
                        if just_crossed_up:
                            last_sell_price = close
                            batch_sells_done = 0
                        if (
                            last_sell_price is not None
                            and close >= last_sell_price * batch_up
                            and batch_sells_done < p.splits
                        ):
                            # 分 splits 次清仓：每次卖 1/剩余次数，最后一次（剩余 1）清光
                            # 等价于 cycle_start/splits 的 N 等份，但「最后一次=全部」杜绝尾数
                            remaining_steps = p.splits - batch_sells_done
                            sell_shares = holding / Decimal(remaining_steps)
                            last_sell_price = close
                            batch_sells_done += 1

                    if sell_shares > 0:
                        sell_shares = min(sell_shares, holding)
                        avg_cost = deployed_cost / holding if holding > 0 else Decimal(0)
                        proceeds = (sell_shares * close).quantize(_Q2)
                        cost_of_sold = (sell_shares * avg_cost).quantize(_Q2)
                        holding -= sell_shares
                        deployed_cost -= cost_of_sold
                        cash += proceeds
                        if holding <= 0:  # 清仓时消除分厘误差
                            holding = Decimal(0)
                            deployed_cost = Decimal(0)
                        action_shares = -sell_shares
                        action_amount = proceeds
                        signal = "sell"
                        sell_count += 1
                        if proceeds > cost_of_sold:
                            profitable_sells += 1

        prev_above_ma = above_ma

        market_value = (holding * close + cash).quantize(_Q2)
        pnl = (market_value - cum_invested).quantize(_Q2)
        return_rate = (
            ((pnl / cum_invested) * Decimal(100)).quantize(_Q4) if cum_invested > 0 else Decimal(0)
        )
        price_vs_ma = (
            ((close - ma) / ma * Decimal(100)).quantize(_Q4) if (ma and ma > 0) else None
        )

        calc_rows.append(
            CalcMa120Backtest(
                task_id=task_id,
                trade_date=d,
                signal=signal,
                action_shares=action_shares.quantize(_Q8),
                action_amount=action_amount.quantize(_Q2),
                holding_shares=holding.quantize(_Q8),
                cash_balance=cash.quantize(_Q2),
                cum_invested=cum_invested.quantize(_Q2),
                market_value=market_value,
                pnl=pnl,
                return_rate=return_rate,
                ma_value=ma if (ma and ma > 0) else None,
                price_vs_ma=price_vs_ma,
            )
        )
        market_values.append(float(market_value))
        prev_close = close

    if calc_rows:
        last_date = calc_rows[-1].trade_date
        cashflows.append((last_date, market_values[-1]))

    counts = (buy_count, sell_count, profitable_sells, dividend_total)
    return calc_rows, market_values, cashflows, counts


def _build_summary(task_id, p, dates, market_values, cashflows, counts):
    total_invested = -sum(cf[1] for cf in cashflows if cf[1] < 0)
    final_value = market_values[-1] if market_values else 0.0
    total_pnl = final_value - total_invested
    total_return_rate = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

    annualized = annualized_return(cashflows, total_return_rate, dates)
    mdd_val = max_drawdown(market_values)

    buy_count, sell_count, profitable_sells, dividend_total = counts
    win_rate = (profitable_sells / sell_count * 100) if sell_count > 0 else 0.0

    return ResultMa120Summary(
        task_id=task_id,
        symbol=p.symbol,
        capital_mode=p.capital_mode,
        principal=p.principal,
        monthly_amount=p.monthly_amount,
        splits=p.splits,
        ma_period=p.ma_period,
        buy_threshold=p.buy_threshold,
        step=p.step,
        sell_mode=p.sell_mode,
        start_date=p.start_date,
        end_date=p.end_date,
        total_invested=Decimal(str(total_invested)).quantize(_Q2),
        final_value=Decimal(str(final_value)).quantize(_Q2),
        total_pnl=Decimal(str(total_pnl)).quantize(_Q2),
        total_return_rate=Decimal(str(round(total_return_rate, 4))),
        annualized_return=Decimal(str(round(annualized, 4))),
        max_drawdown=Decimal(str(round(mdd_val, 4))),
        buy_count=buy_count,
        sell_count=sell_count,
        dividend_total=dividend_total.quantize(_Q2),
        win_rate=Decimal(str(round(win_rate, 4))),
    )


def _write_results(
    db: Session, task_id: str, calc_rows: list[CalcMa120Backtest], summary: ResultMa120Summary
):
    db.execute(delete(CalcMa120Backtest).where(CalcMa120Backtest.task_id == task_id))
    db.execute(delete(ResultMa120Summary).where(ResultMa120Summary.task_id == task_id))
    db.add_all(calc_rows)
    db.add(summary)
    db.commit()
