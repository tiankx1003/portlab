<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import MetricCard from '../components/MetricCard.vue'
import DateInput from '../components/DateInput.vue'
import GridChart from '../components/GridChart.vue'
import {
  createGrid,
  getGridChart,
  getGridSummary,
  runGridPreview,
  searchSymbols,
  type BoundMode,
  type GridChartData,
  type GridSummaryData,
  type SymbolItem,
} from '../api'
import { parseGridTaskId } from '../utils/taskId'

const route = useRoute()

// A 股配色惯例：红涨绿跌
const COLOR_UP = '#ee6666'
const COLOR_DOWN = '#3ba272'

const symbol = ref('510300')
const startDate = ref('2022-01-01')
const endDate = ref(new Date().toISOString().slice(0, 10))
const centerPrice = ref(4.0) // 网格中枢价（参考标的首日收盘，可改）
const stepPct = ref(3) // 网格间距 %
const amountPerLevel = ref(5000) // 每格资金
const nLevelsAbove = ref(5)
const nLevelsBelow = ref(5)
const boundMode = ref<BoundMode>('hold')

const loading = ref(false)
const saving = ref(false)
const savedMsg = ref('')
const errorMsg = ref('')
const chartData = ref<GridChartData | null>(null)
const summary = ref<GridSummaryData | null>(null)

// ---- 标的搜索（带去抖）----
const suggestions = ref<SymbolItem[]>([])
let debounce: ReturnType<typeof setTimeout> | undefined
function onSymbolInput() {
  clearTimeout(debounce)
  const q = normalizedSymbol.value || symbol.value.trim()
  if (!q) {
    suggestions.value = []
    return
  }
  debounce = setTimeout(async () => {
    try {
      const r = await searchSymbols(q)
      suggestions.value = r.code === 0 ? r.data : []
    } catch {
      suggestions.value = []
    }
  }, 250)
}

function detectMarket(code: string): string {
  const c = code.trim()
  if (!/^\d{6}$/.test(c)) return ''
  const h2 = c.slice(0, 2)
  if (['60', '68', '51', '52', '56', '58', '50', '90', '11', '13'].includes(h2)) return 'SH'
  if (['00', '30', '15', '16', '18', '20'].includes(h2)) return 'SZ'
  if (['43', '83', '87', '92'].includes(h2)) return 'BJ'
  if (c[0] === '6' || c[0] === '5' || c[0] === '9') return 'SH'
  if (c[0] === '0' || c[0] === '3') return 'SZ'
  if (c[0] === '4' || c[0] === '8') return 'BJ'
  return ''
}

const normalizedSymbol = computed(() =>
  symbol.value.trim().replace(/^(sh|sz|bj)/i, '').toUpperCase(),
)

const symbolHint = computed(() => {
  const code = normalizedSymbol.value
  if (!/^\d{6}$/.test(code)) return ''
  const m = detectMarket(code)
  if (!m) return ''
  const hit = suggestions.value.find((s) => s.code === code)
  return hit ? `.${m}  ${hit.name}` : `.${m}`
})

function validate(): string {
  const code = normalizedSymbol.value
  if (!code) return '请填写有效的标的代码'
  if (!centerPrice.value || centerPrice.value <= 0) return '网格中枢价需 > 0（可参考区间首日收盘）'
  if (startDate.value >= endDate.value) return '起始日期需早于结束日期'
  return ''
}

function buildParams() {
  return {
    symbol: normalizedSymbol.value,
    start_date: startDate.value,
    end_date: endDate.value,
    center_price: centerPrice.value,
    step_pct: stepPct.value,
    amount_per_level: amountPerLevel.value,
    n_levels_above: nLevelsAbove.value,
    n_levels_below: nLevelsBelow.value,
    bound_mode: boundMode.value,
  }
}

// 实时预览（不落库）：「开始回测」按钮触发
async function runBacktest() {
  errorMsg.value = ''
  chartData.value = null
  summary.value = null
  const err = validate()
  if (err) {
    errorMsg.value = err
    return
  }
  loading.value = true
  try {
    const r = await runGridPreview(buildParams())
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    const { summary: s, ...chart } = r.data
    chartData.value = chart
    summary.value = s
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

// 保存落库（POST /grid，幂等）：「保存」按钮触发，返回 task_id 供首页/直达消费
async function save() {
  errorMsg.value = ''
  savedMsg.value = ''
  const err = validate()
  if (err) {
    errorMsg.value = err
    return
  }
  saving.value = true
  try {
    const r = await createGrid(buildParams())
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    savedMsg.value = `已保存（task_id：${r.data.task_id.slice(0, 24)}…），可从首页「最近记录」查看`
    setTimeout(() => (savedMsg.value = ''), 6000)
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

// 012 回测直达：从 URL ?task= 预载已有结果，并尽量回填表单参数
async function loadTask(taskId: string) {
  loading.value = true
  errorMsg.value = ''
  chartData.value = null
  summary.value = null
  try {
    const parsed = parseGridTaskId(taskId)
    if (parsed) {
      symbol.value = parsed.symbol
      startDate.value = parsed.startDate
      endDate.value = parsed.endDate
      centerPrice.value = parsed.centerPrice
      stepPct.value = parsed.stepPct
      amountPerLevel.value = parsed.amountPerLevel
      nLevelsAbove.value = parsed.nLevelsAbove
      nLevelsBelow.value = parsed.nLevelsBelow
      boundMode.value = parsed.boundMode
    }
    const [c, s] = await Promise.all([getGridChart(taskId), getGridSummary(taskId)])
    if (c.code === 0) chartData.value = c.data
    if (s.code === 0) summary.value = s.data
    if (c.code !== 0 && s.code !== 0) errorMsg.value = c.message || s.message
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const t = route.query.task
  if (typeof t === 'string' && t) loadTask(t)
  else runBacktest() // 进入即用默认参数渲染；改参数后点「回测」重跑
})

const chartTitle = computed(() => {
  const code = normalizedSymbol.value || symbol.value.trim()
  const name = chartData.value?.symbol_name
  return `${name || code} · 网格交易策略回测`
})

function fmt(n: number | undefined, d = 2): string {
  if (n == null || Number.isNaN(n)) return '-'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d })
}
function pnlColor(n: number | undefined): string {
  if (n == null) return ''
  return n >= 0 ? COLOR_UP : COLOR_DOWN
}
</script>

<template>
  <section>
    <h1>网格交易策略回测</h1>

    <!-- 参数表单 -->
    <div class="form-card">
      <div class="form-row">
        <label class="symbol-label">
          标的代码
          <div class="symbol-field">
            <input
              v-model="symbol"
              list="symbol-suggestions"
              placeholder="如 510300 / 510880"
              @input="onSymbolInput"
            />
            <span v-if="symbolHint" class="symbol-hint">{{ symbolHint }}</span>
          </div>
          <datalist id="symbol-suggestions">
            <option v-for="s in suggestions" :key="s.code" :value="s.code">{{ s.name }}</option>
          </datalist>
        </label>

        <label>
          中枢价（元）
          <input v-model.number="centerPrice" type="number" min="0.01" step="0.01" />
        </label>
        <label>
          网格间距 %
          <input v-model.number="stepPct" type="number" min="0.1" step="0.5" class="narrow" />
        </label>
        <label>
          每格资金（元）
          <input v-model.number="amountPerLevel" type="number" min="100" step="500" />
        </label>
      </div>

      <div class="form-row">
        <label>
          上方格数
          <input v-model.number="nLevelsAbove" type="number" min="1" max="20" step="1" class="narrow" />
        </label>
        <label>
          下方格数
          <input v-model.number="nLevelsBelow" type="number" min="1" max="20" step="1" class="narrow" />
        </label>
        <label>
          突破处理
          <select v-model="boundMode">
            <option value="hold">等回归</option>
            <option value="stop">止损止盈</option>
            <option value="reset">重置中枢</option>
          </select>
        </label>
        <label>
          起始日期
          <DateInput v-model="startDate" />
        </label>
        <label>
          结束日期
          <DateInput v-model="endDate" />
        </label>
        <button :disabled="loading" class="primary" @click="runBacktest">
          {{ loading ? '回测中…' : '开始回测' }}
        </button>
        <button :disabled="saving" class="primary" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <p v-if="savedMsg" class="ok">{{ savedMsg }}</p>

    <!-- 指标卡片 -->
    <div v-if="summary" class="cards">
      <MetricCard label="累计投入" :value="fmt(summary.total_invested)" />
      <MetricCard label="最终市值" :value="fmt(summary.final_value)" />
      <MetricCard label="累计收益" :value="fmt(summary.total_pnl)" :color="pnlColor(summary.total_pnl)" />
      <MetricCard
        label="累计收益率"
        :value="fmt(summary.total_return_rate) + '%'"
        :color="pnlColor(summary.total_return_rate)"
      />
      <MetricCard
        label="年化收益率"
        :value="fmt(summary.annualized_return) + '%'"
        :color="pnlColor(summary.annualized_return)"
      />
      <MetricCard label="最大回撤" :value="fmt(summary.max_drawdown) + '%'" :color="COLOR_DOWN" />
      <MetricCard
        label="网格套利"
        :value="fmt(summary.grid_profit)"
        :color="pnlColor(summary.grid_profit)"
      />
      <MetricCard label="完成循环" :value="String(summary.cycle_count)" />
      <div class="trade-card">
        <div class="tc-label">买 / 卖 次数</div>
        <div class="trade-value">
          <span class="num-buy">{{ summary.buy_count }}</span>
          <span class="sep">/</span>
          <span class="num-sell">{{ summary.sell_count }}</span>
        </div>
      </div>
    </div>

    <!-- 图表 -->
    <div v-if="chartData" class="chart-card">
      <h3>{{ chartTitle }}</h3>
      <GridChart :data="chartData" />
    </div>
  </section>
</template>

<style scoped>
.form-card {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 16px 20px;
  background: var(--surface);
  margin: 16px 0;
}
.form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
  margin-bottom: 12px;
}
.form-row:last-child {
  margin-bottom: 0;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 13px;
  color: var(--text-secondary);
  gap: 4px;
}
.symbol-label {
  min-width: 260px;
}
.symbol-field {
  display: flex;
  align-items: center;
  gap: 10px;
}
input,
select {
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  font-size: 14px;
  min-width: 150px;
  background: var(--input-bg);
  color: var(--text);
}
input.narrow {
  min-width: 88px;
  max-width: 100px;
}
.symbol-field input {
  min-width: 160px;
}
.symbol-hint {
  font-size: 13px;
  color: var(--hint);
  white-space: nowrap;
}
button.primary {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 9px 22px;
  font-size: 14px;
  cursor: pointer;
  height: 38px;
}
button.primary:disabled {
  background: var(--primary-disabled);
  cursor: not-allowed;
}
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 16px 0;
}
.trade-card {
  flex: 1 1 0;
  min-width: 150px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--surface);
}
.tc-label {
  font-size: 12px;
  color: var(--text-tertiary);
}
.trade-value {
  margin-top: 4px;
  display: flex;
  align-items: flex-end;
  gap: 6px;
  line-height: 1.2;
}
.num-buy,
.num-sell,
.sep {
  font-size: 22px;
  font-weight: 700;
  line-height: 1;
}
.num-buy {
  color: #ee6666;
}
.num-sell {
  color: #3a7afe;
}
.sep {
  color: var(--text-tertiary);
}
.chart-card {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 16px 20px;
  background: var(--surface);
}
.chart-card h3 {
  margin: 0 0 8px;
  font-size: 16px;
}
.ok {
  color: #2f8a5f;
  background: color-mix(in srgb, #3ba272 14%, transparent);
  border: 1px solid color-mix(in srgb, #3ba272 30%, transparent);
  border-radius: 6px;
  padding: 8px 12px;
}
.err {
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
