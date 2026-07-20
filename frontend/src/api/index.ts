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

// ---- grid backtest ----
export type BoundMode = 'hold' | 'stop' | 'reset'

export interface GridParams {
  symbol: string
  start_date: string
  end_date: string
  center_price: number
  step_pct: number
  amount_per_level: number
  n_levels_above: number
  n_levels_below: number
  bound_mode: BoundMode
}

export interface GridPoint {
  date: string
  price: number
  amount: number
}

export interface GridChartData {
  dates: string[]
  close_prices: number[]
  market_values: number[]
  total_cost: number[]
  pnl: number[]
  return_rates: number[]
  holding: number[]
  signals: string[]
  grid_levels: number[]
  buy_points: GridPoint[]
  sell_points: GridPoint[]
  grid_index: number[]
  benchmark_returns: (number | null)[]
  benchmark_name: string
  symbol_name: string
}

export interface GridSummaryData {
  total_invested: number
  final_value: number
  total_pnl: number
  total_return_rate: number
  annualized_return: number
  max_drawdown: number
  buy_count: number
  sell_count: number
  grid_profit: number
  cycle_count: number
  center_price: number
  step_pct: number
  amount_per_level: number
  n_levels_above: number
  n_levels_below: number
  bound_mode: string
}

export async function createGrid(p: GridParams): Promise<ApiResponse<{ task_id: string }>> {
  const res = await http.post<ApiResponse<{ task_id: string }>>('/backtest/grid', p)
  return res.data
}

export async function getGridChart(taskId: string): Promise<ApiResponse<GridChartData>> {
  const res = await http.get<ApiResponse<GridChartData>>(`/backtest/grid/${taskId}/chart`)
  return res.data
}

export async function getGridSummary(taskId: string): Promise<ApiResponse<GridSummaryData>> {
  const res = await http.get<ApiResponse<GridSummaryData>>(`/backtest/grid/${taskId}/summary`)
  return res.data
}

// ---- portfolio backtest ----
export interface PortfolioParams {
  symbols: string[]
  start_date: string
  end_date: string
  mode: 'fixed' | 'frontier'
  weights: number[]
  rebalance: 'monthly' | 'quarterly' | 'none'
  rf: number
  allow_short: boolean
}

export interface FrontierPoint {
  weights: number[]
  ret: number
  volatility: number
  sharpe: number
}

export interface SingleAssetPoint {
  symbol: string
  name: string
  ret: number
  volatility: number
  sharpe: number
}

export interface FrontierData {
  volatilities: number[]
  returns: number[]
  sharpes: number[]
  weights_matrix: number[][]
  single_assets: SingleAssetPoint[]
  min_variance: FrontierPoint
  max_sharpe: FrontierPoint
  opt_weights: number[]
}

export interface PortfolioChartData {
  dates: string[]
  nav: number[]
  drawdown: number[]
  benchmark_nav: (number | null)[]
  benchmark_name: string
  correlation_symbols: string[]
  correlation_matrix: number[][]
  mode: string
  symbols_name: string[]
  frontier: FrontierData | null
}

export interface PortfolioSummaryData {
  symbols: string[]
  mode: string
  weights: number[]
  rebalance: string
  annual_return: number
  annual_volatility: number
  sharpe: number
  max_drawdown: number
  total_return: number
  rf: number
  allow_short: boolean
}

export async function createPortfolio(p: PortfolioParams): Promise<ApiResponse<{ task_id: string }>> {
  const res = await http.post<ApiResponse<{ task_id: string }>>('/backtest/portfolio', p)
  return res.data
}

export async function getPortfolioChart(taskId: string): Promise<ApiResponse<PortfolioChartData>> {
  const res = await http.get<ApiResponse<PortfolioChartData>>(`/backtest/portfolio/${taskId}/chart`)
  return res.data
}

export async function getPortfolioSummary(
  taskId: string,
): Promise<ApiResponse<PortfolioSummaryData>> {
  const res = await http.get<ApiResponse<PortfolioSummaryData>>(`/backtest/portfolio/${taskId}/summary`)
  return res.data
}

// ---- arena（策略擂台）----
export interface StrategyResultItem {
  task_id: string
  strategy: string
  symbol: string
  symbol_name: string
  start_date: string
  end_date: string
  total_return_rate: number
  annualized_return: number
  max_drawdown: number
  sharpe: number | null
  buy_count: number
  sell_count: number
  params_summary: string
}

export interface ArenaNavSeries {
  dates: string[]
  nav: number[]
}

export interface ArenaData {
  items: StrategyResultItem[]
  nav_series: Record<string, ArenaNavSeries>
}

export async function compareArena(params: {
  mode: 'cross_strategy' | 'cross_symbol'
  symbol?: string
  strategy?: string
  symbols?: string[]
  start?: string
  end?: string
}): Promise<ApiResponse<ArenaData>> {
  const res = await http.get<ApiResponse<ArenaData>>('/arena/compare', { params })
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
  type: 'dca' | 'ma120' | 'drawboard' | 'grid'
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

// ---- drawboard: 基于最大回撤买入策略看板（015 → 019 v2）----
export type DrawSellMode = 'none' | 'new_high' | 'partial'

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
  annualized_return: number
  max_drawdown: number
  buy_count: number
  sell_count: number
  sell_mode: DrawSellMode
}

// 图表数据（实时 GET /backtest 与 DB GET /{task_id}/chart 同构，对齐 Ma120ChartData）
export interface DrawboardChartData {
  dates: string[]
  market_values: number[]
  total_cost: number[]
  pnl: number[]
  return_rates: number[]
  close_prices: number[]
  drawdown: number[]
  holding: number[]
  signals: string[]
  buy_points: DrawPoint[]
  sell_points: DrawPoint[]
  benchmark_returns: (number | null)[]
  benchmark_name: string
  symbol_name: string
}

// 实时 GET /backtest = 图表数据 + 汇总
export interface DrawBacktestResult extends DrawboardChartData {
  summary: DrawSummary
}

export interface DrawboardParams {
  symbol: string
  start_date: string
  end_date: string
  threshold: number
  step: number
  buy_amount: number
  add_amount: number
  sell_mode: DrawSellMode
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
  sell_mode: DrawSellMode
}): Promise<ApiResponse<DrawBacktestResult>> {
  const res = await http.get<ApiResponse<DrawBacktestResult>>('/drawboard/backtest', {
    params,
  })
  return res.data
}

/** 保存落库（POST /save）：命中缓存或计算 → 返回 task_id。 */
export async function saveDrawboard(
  params: DrawboardParams,
): Promise<ApiResponse<{ task_id: string }>> {
  const res = await http.post<ApiResponse<{ task_id: string }>>('/drawboard/save', params)
  return res.data
}

/** 读 calc_drawboard_backtest 逐日（图表数据，结构与实时 GET 一致）。 */
export async function getDrawboardChart(
  taskId: string,
): Promise<ApiResponse<DrawboardChartData>> {
  const res = await http.get<ApiResponse<DrawboardChartData>>(`/drawboard/${taskId}/chart`)
  return res.data
}

/** 读 result_drawboard_summary 汇总。 */
export async function getDrawboardSummary(taskId: string): Promise<ApiResponse<DrawSummary>> {
  const res = await http.get<ApiResponse<DrawSummary>>(`/drawboard/${taskId}/summary`)
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

// ---- event dashboard: 事件冲击产业链看板（018）----
export type ChainRole = 'upstream' | 'midstream' | 'downstream'
export type Relevance = 'high' | 'medium' | 'low' | 'none'

export interface ThemeBrief {
  id: number
  name: string
  is_builtin: boolean
  keywords: string | null
  stock_count: number
}
export interface ThemeStockItem {
  symbol: string
  name: string
  chain_role: ChainRole
  weight: number
}
export interface ThemeDetail {
  id: number
  name: string
  is_builtin: boolean
  keywords: string | null
  stocks: ThemeStockItem[]
}
export interface LlmConfigStatus {
  enabled: boolean
  api_base: string
  api_key_masked: string
  model: string
  configured: boolean
  test?: string | null
}
export interface MatchedStock {
  symbol: string
  name: string
  chain_role: ChainRole
  weight: number
  relevance: Relevance
}
export interface ConceptStock {
  symbol: string
  name: string
}
export interface EventStockOut {
  symbol: string
  name: string
  chain_role: ChainRole
}
export interface EventBrief {
  id: number
  name: string
  event_date: string
  description: string | null
  theme_id: number | null
  stocks: EventStockOut[]
}
export interface EventStockInput {
  symbol: string
  chain_role: ChainRole
}
export interface SymbolInfo {
  symbol: string
  name: string
  chain_role: ChainRole
}
export interface RankingItem {
  symbol: string
  name: string
  change_pct: number
  chain_role: ChainRole
}
export interface WindowReturnSeries {
  dates: string[]
  returns: number[]
}
export interface ChainGroups {
  upstream: string[]
  midstream: string[]
  downstream: string[]
}
export interface EventImpactData {
  event_id: number
  event_name: string
  event_date: string
  before: number
  after: number
  symbols_info: SymbolInfo[]
  window_returns: Record<string, WindowReturnSeries>
  benchmark_symbol: string | null
  benchmark_name: string | null
  benchmark_series: WindowReturnSeries | null
  ranking: RankingItem[]
  correlation_symbols: string[]
  correlation_matrix: number[][]
  chain_groups: ChainGroups
  missing: string[]
}

export async function listThemes(): Promise<ApiResponse<ThemeBrief[]>> {
  const res = await http.get<ApiResponse<ThemeBrief[]>>('/event/themes')
  return res.data
}
export async function getTheme(id: number): Promise<ApiResponse<ThemeDetail>> {
  const res = await http.get<ApiResponse<ThemeDetail>>(`/event/themes/${id}`)
  return res.data
}
export async function getLlmConfig(): Promise<ApiResponse<LlmConfigStatus>> {
  const res = await http.get<ApiResponse<LlmConfigStatus>>('/event/llm-config')
  return res.data
}
export async function updateLlmConfig(
  body: Partial<{ api_base: string; api_key: string; model: string; enabled: boolean }> & {
    test?: boolean
  },
): Promise<ApiResponse<LlmConfigStatus>> {
  const test = body.test ? { test: 'true' } : undefined
  const { test: _omit, ...payload } = body
  const res = await http.put<ApiResponse<LlmConfigStatus>>('/event/llm-config', payload, {
    params: test,
  })
  return res.data
}
export async function smartMatch(body: {
  event_name: string
  description?: string | null
}): Promise<ApiResponse<MatchedStock[]>> {
  const res = await http.post<ApiResponse<MatchedStock[]>>('/event/smart-match', body)
  return res.data
}
export async function listConceptStocks(
  concept: string,
): Promise<ApiResponse<ConceptStock[]>> {
  const res = await http.get<ApiResponse<ConceptStock[]>>('/event/concept-stocks', {
    params: { concept },
  })
  return res.data
}
export async function createEvent(body: {
  name: string
  event_date: string
  description?: string | null
  theme_id?: number | null
  stocks?: EventStockInput[]
}): Promise<ApiResponse<EventBrief>> {
  const res = await http.post<ApiResponse<EventBrief>>('/event', body)
  return res.data
}
export async function getEvent(id: number): Promise<ApiResponse<EventBrief>> {
  const res = await http.get<ApiResponse<EventBrief>>(`/event/${id}`)
  return res.data
}
export async function updateEventStocks(
  id: number,
  stocks: EventStockInput[],
): Promise<ApiResponse<EventBrief>> {
  const res = await http.put<ApiResponse<EventBrief>>(`/event/${id}/stocks`, { stocks })
  return res.data
}
export async function getEventImpact(
  id: number,
  params: { before: number; after: number },
): Promise<ApiResponse<EventImpactData>> {
  const res = await http.get<ApiResponse<EventImpactData>>(`/event/${id}/impact`, { params })
  return res.data
}

export default http
