/** task_id 解析：从回测 task_id 反推表单参数（用于 012 回测直达 ?task= 预载回填）。
 *
 * 约定与后端 make_task_id 一致；非 akshare 源末尾追加 _{source}（如 _tushare）。
 * 解析失败返回 null（调用方仅展示结果、不回填）。
 */

function toIsoDate(yyyymmdd: string): string {
  if (!/^\d{8}$/.test(yyyymmdd)) return ''
  return `${yyyymmdd.slice(0, 4)}-${yyyymmdd.slice(4, 6)}-${yyyymmdd.slice(6, 8)}`
}

function stripSourceSuffix(parts: string[]): string[] {
  if (parts.length && parts[parts.length - 1] === 'tushare') return parts.slice(0, -1)
  return parts
}

export interface DcaTaskParts {
  symbol: string
  startDate: string
  endDate: string
  frequency: 'weekly' | 'monthly'
  amount: number
  investDay: number
  mode: 'normal' | 'smart'
  maPeriod: number
}

/** dca_{symbol}_{start}_{end}_{frequency}_{amount}_{invest_day}_{mode}_{ma_period} */
export function parseDcaTaskId(taskId: string): DcaTaskParts | null {
  const parts = stripSourceSuffix(taskId.split('_'))
  if (parts.length < 9 || parts[0] !== 'dca') return null
  const [, symbol, start, end, frequency, amount, investDay, mode, maPeriod] = parts
  if (frequency !== 'weekly' && frequency !== 'monthly') return null
  if (mode !== 'normal' && mode !== 'smart') return null
  const sd = toIsoDate(start)
  const ed = toIsoDate(end)
  if (!sd || !ed) return null
  return {
    symbol,
    startDate: sd,
    endDate: ed,
    frequency,
    amount: Number(amount),
    investDay: Number(investDay),
    mode,
    maPeriod: Number(maPeriod),
  }
}

export interface Ma120TaskParts {
  symbol: string
  startDate: string
  endDate: string
  capitalMode: 'fixed' | 'recurring' | 'hybrid'
  principal: number | null
  monthly: number | null
  splits: number
  maPeriod: number
  buyThreshold: number
  step: number
  sellMode: 'batch' | 'all' | 'half'
  crashThreshold: number
  crashMultiplier: number
  dividendMode: 'cash' | 'reinvest'
  batchSellStep: number
}

/**
 * ma120_{symbol}_{start}_{end}_{capital_mode}_{principal}_{monthly}_{splits}
 * _{ma_period}_{buy_threshold}_{step}_{sell_mode}_{crash_threshold}_{crash_multiplier}
 * _{dividend_mode}_{batch_sell_step}
 */
export function parseMa120TaskId(taskId: string): Ma120TaskParts | null {
  const parts = stripSourceSuffix(taskId.split('_'))
  if (parts.length < 16 || parts[0] !== 'ma120') return null
  const [, symbol, start, end, capitalMode, principal, monthly, splits, maPeriod, buyThreshold,
    step, sellMode, crashThreshold, crashMultiplier, dividendMode, batchSellStep] = parts
  if (!['fixed', 'recurring', 'hybrid'].includes(capitalMode)) return null
  if (!['batch', 'all', 'half'].includes(sellMode)) return null
  if (!['cash', 'reinvest'].includes(dividendMode)) return null
  const sd = toIsoDate(start)
  const ed = toIsoDate(end)
  if (!sd || !ed) return null
  return {
    symbol,
    startDate: sd,
    endDate: ed,
    capitalMode: capitalMode as Ma120TaskParts['capitalMode'],
    principal: principal === '0' ? null : Number(principal),
    monthly: monthly === '0' ? null : Number(monthly),
    splits: Number(splits),
    maPeriod: Number(maPeriod),
    buyThreshold: Number(buyThreshold),
    step: Number(step),
    sellMode: sellMode as Ma120TaskParts['sellMode'],
    crashThreshold: Number(crashThreshold),
    crashMultiplier: Number(crashMultiplier),
    dividendMode: dividendMode as Ma120TaskParts['dividendMode'],
    batchSellStep: Number(batchSellStep),
  }
}

export interface DrawboardTaskParts {
  symbol: string
  startDate: string
  endDate: string
  threshold: number
  step: number
  buyAmount: number
  addAmount: number
  sellMode: 'none' | 'new_high' | 'partial'
}

/**
 * db_{symbol}_{start}_{end}_{threshold}_{step}_{buy_amount}_{add_amount}_{sell_mode}
 * 与后端 services/drawboard.make_task_id 一致；非 akshare 源末尾追加 _{source}。
 */
export function parseDrawboardTaskId(taskId: string): DrawboardTaskParts | null {
  const parts = stripSourceSuffix(taskId.split('_'))
  if (parts.length < 9 || parts[0] !== 'db') return null
  const [, symbol, start, end, threshold, step, buyAmount, addAmount, sellMode] = parts
  if (!['none', 'new_high', 'partial'].includes(sellMode)) return null
  const sd = toIsoDate(start)
  const ed = toIsoDate(end)
  if (!sd || !ed) return null
  return {
    symbol,
    startDate: sd,
    endDate: ed,
    threshold: Number(threshold),
    step: Number(step),
    buyAmount: Number(buyAmount),
    addAmount: Number(addAmount),
    sellMode: sellMode as DrawboardTaskParts['sellMode'],
  }
}

export interface GridTaskParts {
  symbol: string
  startDate: string
  endDate: string
  centerPrice: number
  stepPct: number
  amountPerLevel: number
  nLevelsAbove: number
  nLevelsBelow: number
  boundMode: 'hold' | 'stop' | 'reset'
}

/**
 * grid_{symbol}_{start}_{end}_{center}_{step_pct}_{amount}_{n_above}_{n_below}_{bound_mode}
 * 与后端 services.compute.grid.make_task_id 一致；非 akshare 源末尾追加 _{source}。
 */
export function parseGridTaskId(taskId: string): GridTaskParts | null {
  const parts = stripSourceSuffix(taskId.split('_'))
  if (parts.length < 10 || parts[0] !== 'grid') return null
  const [, symbol, start, end, center, stepPct, amount, nAbove, nBelow, mode] = parts
  if (!['hold', 'stop', 'reset'].includes(mode)) return null
  const sd = toIsoDate(start)
  const ed = toIsoDate(end)
  if (!sd || !ed) return null
  return {
    symbol,
    startDate: sd,
    endDate: ed,
    centerPrice: Number(center),
    stepPct: Number(stepPct),
    amountPerLevel: Number(amount),
    nLevelsAbove: Number(nAbove),
    nLevelsBelow: Number(nBelow),
    boundMode: mode as GridTaskParts['boundMode'],
  }
}
