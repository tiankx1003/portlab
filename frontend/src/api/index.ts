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

export default http
