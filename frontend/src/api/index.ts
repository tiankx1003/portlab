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

export default http
