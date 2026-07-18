import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

// ---- health ----
export async function getHealth(): Promise<ApiResponse<{ status: string }>> {
  const res = await http.get<ApiResponse<{ status: string }>>('/health')
  return res.data
}

// ---- symbols ----
export interface SymbolItem {
  code: string
  name: string
  type: string
}

export async function searchSymbols(q: string): Promise<ApiResponse<SymbolItem[]>> {
  const res = await http.get<ApiResponse<SymbolItem[]>>('/symbols/search', { params: { q } })
  return res.data
}

// ---- backtest ----
export interface BacktestParams {
  symbol: string
  frequency: 'weekly' | 'monthly'
  amount: number
  start_date: string
  end_date: string
  invest_day: number
  mode: 'normal' | 'smart'
  ma_period: number
}

export interface ChartData {
  dates: string[]
  market_value: number[]
  total_cost: number[]
  pnl: number[]
  return_rate: number[]
  invest_days: boolean[]
  deduction_rates: (number | null)[]
  actual_amounts: (number | null)[]
  benchmark_returns: (number | null)[]
  benchmark_name: string
  symbol_name: string
}

export interface SummaryData {
  total_invested: number
  final_value: number
  total_pnl: number
  total_return_rate: number
  annualized_return: number
  max_drawdown: number
  invest_count: number
  symbol_name: string
}

export async function createBacktest(p: BacktestParams): Promise<ApiResponse<{ task_id: string }>> {
  const res = await http.post<ApiResponse<{ task_id: string }>>('/backtest/dca', p)
  return res.data
}

export async function getChart(taskId: string): Promise<ApiResponse<ChartData>> {
  const res = await http.get<ApiResponse<ChartData>>(`/backtest/dca/${taskId}/chart`)
  return res.data
}

export async function getSummary(taskId: string): Promise<ApiResponse<SummaryData>> {
  const res = await http.get<ApiResponse<SummaryData>>(`/backtest/dca/${taskId}/summary`)
  return res.data
}

// ---- ma120 backtest ----
export type CapitalMode = 'fixed' | 'recurring' | 'hybrid'
export type SellMode = 'batch' | 'all' | 'half'
export type DividendMode = 'cash' | 'reinvest'

export interface Ma120Params {
  symbol: string
  start_date: string
  end_date: string
  capital_mode: CapitalMode
  principal?: number | null
  monthly_amount?: number | null
  splits: number
  ma_period: number
  buy_threshold: number
  step: number
  crash_threshold: number
  crash_multiplier: number
  sell_mode: SellMode
  batch_sell_step: number
  dividend_mode: DividendMode
}

export interface Ma120Point {
  date: string
  price: number
  amount: number
}

export interface Ma120ChartData {
  dates: string[]
  market_value: number[]
  total_cost: number[]
  pnl: number[]
  return_rate: number[]
  ma_values: (number | null)[]
  close_prices: (number | null)[]
  holding_shares: number[]
  price_vs_ma: (number | null)[]
  signals: string[]
  buy_points: Ma120Point[]
  sell_points: Ma120Point[]
  benchmark_returns: (number | null)[]
  benchmark_name: string
  symbol_name: string
}

export interface Ma120SummaryData {
  total_invested: number
  final_value: number
  total_pnl: number
  total_return_rate: number
  annualized_return: number
  max_drawdown: number
  buy_count: number
  sell_count: number
  dividend_total: number
  win_rate: number
  symbol_name: string
}

export async function createMa120(
  p: Ma120Params,
): Promise<ApiResponse<{ task_id: string }>> {
  const res = await http.post<ApiResponse<{ task_id: string }>>('/backtest/ma120', p)
  return res.data
}

export async function getMa120Chart(taskId: string): Promise<ApiResponse<Ma120ChartData>> {
  const res = await http.get<ApiResponse<Ma120ChartData>>(`/backtest/ma120/${taskId}/chart`)
  return res.data
}

export async function getMa120Summary(
  taskId: string,
): Promise<ApiResponse<Ma120SummaryData>> {
  const res = await http.get<ApiResponse<Ma120SummaryData>>(`/backtest/ma120/${taskId}/summary`)
  return res.data
}

// ---- feedback ----
export interface FeedbackItem {
  id: number
  content: string
  nickname: string | null
  created_at: string
  expires_at: string
}

export async function listFeedback(): Promise<ApiResponse<FeedbackItem[]>> {
  const res = await http.get<ApiResponse<FeedbackItem[]>>('/feedback')
  return res.data
}

export async function submitFeedback(body: {
  content: string
  nickname?: string | null
}): Promise<ApiResponse<{ id: number }>> {
  const res = await http.post<ApiResponse<{ id: number }>>('/feedback', body)
  return res.data
}

export async function deleteFeedback(id: number): Promise<ApiResponse<null>> {
  const res = await http.delete<ApiResponse<null>>(`/feedback/${id}`)
  return res.data
}

// ---- release notes ----
export type ReleaseNoteType = 'feature' | 'bugfix' | 'improvement' | 'notice'

export interface ReleaseNoteItem {
  id: number
  title: string
  type: ReleaseNoteType
  detail: string | null
  released_at: string
}

export async function listReleaseNotes(): Promise<ApiResponse<ReleaseNoteItem[]>> {
  const res = await http.get<ApiResponse<ReleaseNoteItem[]>>('/release-notes')
  return res.data
}

// ---- datasource ----
export interface DataSourceStatus {
  tushare_enabled: boolean
  active_source: string
  tushare_token_masked: string
  tushare_configured: boolean
}

export async function getDataSourceStatus(): Promise<ApiResponse<DataSourceStatus>> {
  const res = await http.get<ApiResponse<DataSourceStatus>>('/datasource/status')
  return res.data
}

export async function updateTushareToken(body: {
  token: string
}): Promise<ApiResponse<DataSourceStatus>> {
  const res = await http.put<ApiResponse<DataSourceStatus>>('/datasource/token', body)
  return res.data
}

export async function clearTushareToken(): Promise<ApiResponse<DataSourceStatus>> {
  const res = await http.delete<ApiResponse<DataSourceStatus>>('/datasource/token')
  return res.data
}

export async function toggleTushare(enabled: boolean): Promise<ApiResponse<DataSourceStatus>> {
  const res = await http.put<ApiResponse<DataSourceStatus>>('/datasource/toggle', { enabled })
  return res.data
}

// ---- home: recent backtests ----
export interface RecentBacktestItem {
  task_id: string
  type: 'dca' | 'ma120'
  symbol: string
  symbol_name: string
  return_rate: number
  period_text: string
  created_text: string
}

export async function listRecentBacktests(limit = 5): Promise<ApiResponse<RecentBacktestItem[]>> {
  const res = await http.get<ApiResponse<RecentBacktestItem[]>>('/backtest/recent', {
    params: { limit },
  })
  return res.data
}

// ---- home: market overview ----
export interface MarketItem {
  symbol: string
  name: string
  latest_date: string
  latest_close: number
  prev_close: number | null
  change_pct: number | null
  sparkline: number[]
}

export interface MarketOverview {
  as_of: string | null
  items: MarketItem[]
  missing: string[]
}

export async function getMarketOverview(extra?: string): Promise<ApiResponse<MarketOverview>> {
  const res = await http.get<ApiResponse<MarketOverview>>('/market/overview', {
    params: extra ? { extra } : undefined,
  })
  return res.data
}

/** 刷新某指数行情（复用 /api/data/fetch，UPSERT 幂等）。 */
export async function fetchMarketData(
  symbol: string,
  start: string,
  end: string,
): Promise<ApiResponse<{ rows_upserted: number; source: string }>> {
  const res = await http.post<ApiResponse<{ rows_upserted: number; source: string }>>(
    '/data/fetch',
    { symbol, start_date: start, end_date: end },
  )
  return res.data
}

// ---- home: roadmap ----
export interface RoadmapItem {
  id: string
  title: string
  summary: string
  doc_url: string
  category: string
}

export interface Roadmap {
  items: RoadmapItem[]
  total: number
}

export async function getRoadmap(): Promise<ApiResponse<Roadmap>> {
  const res = await http.get<ApiResponse<Roadmap>>('/roadmap')
  return res.data
}

// ---- drawboard: 基于最大回撤买入策略看板（015）----
export interface DrawdownSeries {
  dates: string[]
  prices: number[]
  price_pct: (number | null)[] // 起算至今累计涨幅 %
  drawdown: (number | null)[] // 滚动最大回撤 %（≤0）
  benchmark_dates: string[]
  benchmark_pct: (number | null)[] // 510300 累计涨幅 %
}

export interface DrawPoint {
  date: string
  price: number
  amount: number
}

export interface DrawSummary {
  total_invested: number
  final_value: number
  total_pnl: number
  total_return_rate: number
  buy_count: number
  sell_count: number
}

export interface DrawBacktestResult {
  dates: string[]
  market_values: number[]
  return_rates: number[]
  buy_points: DrawPoint[]
  sell_points: DrawPoint[]
  summary: DrawSummary
}

export async function getDrawdownSeries(
  symbol: string,
  start: string,
  end: string,
): Promise<ApiResponse<DrawdownSeries>> {
  const res = await http.get<ApiResponse<DrawdownSeries>>('/drawboard/series', {
    params: { symbol, start, end },
  })
  return res.data
}

export async function runDrawdownBacktest(params: {
  symbol: string
  start: string
  end: string
  threshold: number
  step: number
  buy_amount: number
  add_amount: number
}): Promise<ApiResponse<DrawBacktestResult>> {
  const res = await http.get<ApiResponse<DrawBacktestResult>>('/drawboard/backtest', {
    params,
  })
  return res.data
}

// ---- etf flow: ETF 资金流向三信号（017，Tushare）----
export interface EtfSignal {
  available: boolean
  reason?: string
  dates?: string[]
  values?: number[]
}

export interface EtfFlowData {
  symbol: string
  name: string
  available: boolean
  as_of: string | null
  signals: Record<string, EtfSignal>
}

export async function getEtfFlow(
  symbol: string,
  start?: string,
  end?: string,
): Promise<ApiResponse<EtfFlowData>> {
  const res = await http.get<ApiResponse<EtfFlowData>>('/etf-flow', {
    params: { symbol, start, end },
  })
  return res.data
}

// ---- valuation: 估值温度计（016）----
export interface ValuationData {
  available: boolean
  reason?: string
  symbol?: string
  name?: string
  current_pe?: number
  percentile?: number // 0~100，越大越贵
  min?: number
  max?: number
  as_of?: string
  series?: [string, number][] // (date, pe)
}

export async function getValuation(symbol: string): Promise<ApiResponse<ValuationData>> {
  const res = await http.get<ApiResponse<ValuationData>>('/valuation', { params: { symbol } })
  return res.data
}

export default http
