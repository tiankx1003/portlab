<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MetricCard from '../components/MetricCard.vue'
import DateInput from '../components/DateInput.vue'
import PortfolioNavChart from '../components/PortfolioNavChart.vue'
import CorrelationHeatmap from '../components/CorrelationHeatmap.vue'
import EfficientFrontierChart from '../components/EfficientFrontierChart.vue'
import WeightPieChart from '../components/WeightPieChart.vue'
import {
  createPortfolio,
  getPortfolioChart,
  getPortfolioSummary,
  searchSymbols,
  type PortfolioChartData,
  type PortfolioSummaryData,
  type SymbolItem,
} from '../api'

const route = useRoute()
const COLOR_UP = '#ee6666'
const COLOR_DOWN = '#3ba272'

// 多标的（默认红利 + 红利低波 + 沪深300）
const symbols = ref<string[]>(['510880', '512890', '510300'])
const symbolInput = ref('')
const suggestions = ref<SymbolItem[]>([])
let debounce: ReturnType<typeof setTimeout> | undefined

const mode = ref<'fixed' | 'frontier'>('fixed')
const weights = ref<number[]>([])
const rebalance = ref<'monthly' | 'quarterly' | 'none'>('monthly')
const rf = ref(0.025)
const allowShort = ref(false)
const startDate = ref('2022-01-01')
const endDate = ref(new Date().toISOString().slice(0, 10))

const loading = ref(false)
const errorMsg = ref('')
const chartData = ref<PortfolioChartData | null>(null)
const summary = ref<PortfolioSummaryData | null>(null)
const selectedFrontierIdx = ref(0) // 前沿点选中（联动饼图）

// 等权初始化（标的数变化时）
function syncEqualWeights() {
  if (mode.value === 'fixed') {
    const eq = 1 / symbols.value.length
    weights.value = symbols.value.map(() => Number(eq.toFixed(4)))
  }
}
watch(symbols, syncEqualWeights, { deep: true })
watch(mode, syncEqualWeights)
syncEqualWeights()

function onSymbolInput() {
  clearTimeout(debounce)
  const q = symbolInput.value.trim().replace(/^(sh|sz|bj)/i, '')
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

function addSymbol(code?: string) {
  const c = (code ?? symbolInput.value).trim().replace(/^(sh|sz|bj)/i, '')
  if (/^\d{6}$/.test(c) && !symbols.value.includes(c)) {
    symbols.value.push(c)
    symbolInput.value = ''
    suggestions.value = []
  }
}

function removeSymbol(i: number) {
  symbols.value.splice(i, 1)
}

// 前沿点选中 → 饼图联动
function onFrontierSelect(idx: number) {
  selectedFrontierIdx.value = idx
}
const pieWeights = computed<number[]>(() => {
  if (mode.value === 'fixed') return weights.value
  const fr = chartData.value?.frontier
  if (!fr) return []
  return fr.weights_matrix[selectedFrontierIdx.value] ?? fr.opt_weights
})
const pieNames = computed(() => chartData.value?.symbols_name ?? symbols.value)

async function runBacktest() {
  errorMsg.value = ''
  chartData.value = null
  summary.value = null
  if (symbols.value.length < 2) {
    errorMsg.value = '组合回测需至少 2 个标的'
    return
  }
  if (startDate.value >= endDate.value) {
    errorMsg.value = '起始日期需早于结束日期'
    return
  }

  loading.value = true
  try {
    const r = await createPortfolio({
      symbols: symbols.value,
      start_date: startDate.value,
      end_date: endDate.value,
      mode: mode.value,
      weights: mode.value === 'fixed' ? weights.value : [],
      rebalance: rebalance.value,
      rf: rf.value,
      allow_short: allowShort.value,
    })
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    const taskId = r.data.task_id
    const [c, s] = await Promise.all([getPortfolioChart(taskId), getPortfolioSummary(taskId)])
    if (c.code === 0) chartData.value = c.data
    if (s.code === 0) summary.value = s.data
    if (c.code !== 0) errorMsg.value = c.message
    selectedFrontierIdx.value = 0
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  const t = route.query.task
  if (typeof t === 'string' && t) {
    // 组合 task_id 含 hash，无法可靠反解参数；仅拉结果展示
    ;(async () => {
      loading.value = true
      try {
        const [c, s] = await Promise.all([getPortfolioChart(t), getPortfolioSummary(t)])
        if (c.code === 0) chartData.value = c.data
        if (s.code === 0) summary.value = s.data
        if (c.code !== 0) errorMsg.value = c.message
      } finally {
        loading.value = false
      }
    })()
  } else {
    runBacktest() // 进入即用默认组合渲染；改参数后点「回测」重跑
  }
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
    <h1>组合回测</h1>

    <div class="form-card">
      <div class="form-row">
        <label class="symbol-label">
          添加标的（回车或点击建议）
          <div class="symbol-field">
            <input
              v-model="symbolInput"
              list="port-symbol-suggestions"
              placeholder="如 510880"
              @input="onSymbolInput"
              @keydown.enter="addSymbol()"
            />
            <button class="add-btn" type="button" @click="addSymbol()">＋</button>
            <datalist id="port-symbol-suggestions">
              <option v-for="s in suggestions" :key="s.code" :value="s.code" @click="addSymbol(s.code)">
                {{ s.name }}
              </option>
            </datalist>
          </div>
        </label>

        <label>
          模式
          <select v-model="mode">
            <option value="fixed">指定权重</option>
            <option value="frontier">有效前沿</option>
          </select>
        </label>

        <label>
          再平衡
          <select v-model="rebalance">
            <option value="monthly">按月</option>
            <option value="quarterly">按季</option>
            <option value="none">不调</option>
          </select>
        </label>

        <label>
          无风险利率
          <input v-model.number="rf" type="number" min="0" max="0.2" step="0.005" class="narrow" />
        </label>

        <label v-if="mode === 'frontier'">
          <span class="cb-label">允许做空
            <input v-model="allowShort" type="checkbox" class="cb" />
          </span>
        </label>
      </div>

      <!-- 标的 chips -->
      <div class="chips">
        <span v-for="(s, i) in symbols" :key="s" class="chip">
          {{ s }}
          <button class="chip-x" type="button" @click="removeSymbol(i)">×</button>
        </span>
        <span v-if="!symbols.length" class="muted">请添加至少 2 个标的</span>
      </div>

      <!-- fixed 模式权重输入 -->
      <div v-if="mode === 'fixed'" class="weights">
        <div v-for="(s, i) in symbols" :key="'w' + s" class="weight-item">
          <span class="w-code">{{ s }}</span>
          <input v-model.number="weights[i]" type="number" min="0" max="1" step="0.05" class="w-input" />
          <span class="w-pct">{{ fmt((weights[i] || 0) * 100, 1) }}%</span>
        </div>
      </div>

      <div class="form-row">
        <label>起始日期<DateInput v-model="startDate" /></label>
        <label>结束日期<DateInput v-model="endDate" /></label>
        <button :disabled="loading" class="primary" @click="runBacktest">
          {{ loading ? '回测中…' : '开始回测' }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

    <div v-if="summary" class="cards">
      <MetricCard label="年化收益" :value="fmt(summary.annual_return) + '%'" :color="pnlColor(summary.annual_return)" />
      <MetricCard label="年化波动" :value="fmt(summary.annual_volatility) + '%'" />
      <MetricCard label="夏普比率" :value="fmt(summary.sharpe)" :color="pnlColor(summary.sharpe)" />
      <MetricCard label="最大回撤" :value="fmt(summary.max_drawdown) + '%'" :color="COLOR_DOWN" />
      <MetricCard label="总收益" :value="fmt(summary.total_return) + '%'" :color="pnlColor(summary.total_return)" />
    </div>

    <div v-if="chartData" class="chart-card">
      <h3>组合净值（起点=1）</h3>
      <PortfolioNavChart :data="chartData" />
    </div>

    <div v-if="chartData?.frontier" class="charts-grid">
      <div class="chart-card">
        <h3>有效前沿（点击点位联动权重饼图）</h3>
        <EfficientFrontierChart :data="chartData.frontier" @select="onFrontierSelect" />
      </div>
      <div class="chart-card">
        <h3>{{ mode === 'frontier' ? '所选前沿点权重' : '指定权重' }}</h3>
        <WeightPieChart :weights="pieWeights" :names="pieNames" />
      </div>
    </div>
    <div v-else-if="chartData" class="chart-card">
      <h3>权重配比</h3>
      <WeightPieChart :weights="pieWeights" :names="pieNames" />
    </div>

    <div v-if="chartData" class="chart-card">
      <h3>标的间相关性</h3>
      <CorrelationHeatmap :data="chartData" />
    </div>
  </section>
</template>

<style scoped>
.form-card { border: 1px solid var(--border-light); border-radius: 8px; padding: 16px 20px; background: var(--surface); margin: 16px 0; }
.form-row { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; margin-bottom: 12px; }
label { display: flex; flex-direction: column; font-size: 13px; color: var(--text-secondary); gap: 4px; }
.symbol-label { min-width: 280px; }
.symbol-field { display: flex; align-items: center; gap: 8px; }
input, select { padding: 8px 10px; border: 1px solid var(--input-border); border-radius: 6px; font-size: 14px; min-width: 130px; background: var(--input-bg); color: var(--text); }
input.narrow { min-width: 88px; max-width: 100px; }
.symbol-field input { min-width: 160px; }
.add-btn { background: var(--primary); color: #fff; border: none; border-radius: 6px; width: 36px; height: 36px; font-size: 18px; cursor: pointer; }
.cb-label { display: flex; flex-direction: row; align-items: center; gap: 6px; }
.cb { min-width: auto; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; }
.chip { background: color-mix(in srgb, var(--primary) 14%, transparent); color: var(--primary); border-radius: 14px; padding: 3px 10px; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; }
.chip-x { background: none; border: none; color: inherit; cursor: pointer; font-size: 15px; line-height: 1; }
.muted { color: var(--text-tertiary); font-size: 13px; }
.weights { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; padding: 10px 0; border-top: 1px dashed var(--border-light); border-bottom: 1px dashed var(--border-light); }
.weight-item { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.w-code { color: var(--text); min-width: 56px; }
.w-input { min-width: 80px !important; }
.w-pct { color: var(--text-secondary); min-width: 48px; }
button.primary { background: var(--primary); color: #fff; border: none; border-radius: 6px; padding: 9px 22px; font-size: 14px; cursor: pointer; height: 38px; }
button.primary:disabled { background: var(--primary-disabled); cursor: not-allowed; }
.cards { display: flex; flex-wrap: wrap; gap: 12px; margin: 16px 0; }
.chart-card { border: 1px solid var(--border-light); border-radius: 8px; padding: 16px 20px; background: var(--surface); margin: 16px 0; }
.chart-card h3 { margin: 0 0 8px; font-size: 16px; }
.charts-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 980px) { .charts-grid { grid-template-columns: 1fr; } }
.err { color: var(--error-text); background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 6px; padding: 8px 12px; }
</style>
