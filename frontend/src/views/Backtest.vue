<script setup lang="ts">
import { computed, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import DcaChart from '../components/DcaChart.vue'
import {
  createBacktest,
  getChart,
  getSummary,
  searchSymbols,
  type ChartData,
  type SummaryData,
  type SymbolItem,
} from '../api'

// A 股配色惯例：红涨绿跌
const COLOR_UP = '#ee6666' // 盈利
const COLOR_DOWN = '#3ba272' // 亏损 / 回撤

const symbol = ref('000001')
const frequency = ref<'weekly' | 'monthly'>('monthly')
const investDay = ref(10)
const amount = ref(1000)
const startDate = ref('2023-01-01')
const endDate = ref(new Date().toISOString().slice(0, 10))
const mode = ref<'normal' | 'smart'>('smart')
const maPeriod = ref(250)

const loading = ref(false)
const errorMsg = ref('')
const chartData = ref<ChartData | null>(null)
const summary = ref<SummaryData | null>(null)

// 扣款率参考表
const highBands = [
  ['0 ~ 2%', '100%'], ['2 ~ 4%', '90%'], ['4 ~ 6%', '80%'],
  ['6 ~ 8%', '70%'], ['8 ~ 10%', '60%'], ['≥ 10%', '50%'],
]
const lowBands = [
  ['-2 ~ 0%', '100%'], ['-4 ~ -2%', '110%'], ['-6 ~ -4%', '120%'],
  ['-8 ~ -6%', '130%'], ['-10 ~ -8%', '140%'], ['-12 ~ -10%', '150%'],
  ['-14 ~ -12%', '160%'], ['-16 ~ -14%', '170%'], ['-18 ~ -16%', '180%'],
  ['-20 ~ -18%', '190%'], ['< -20%', '200%'],
]

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

// ---- 市场识别 ----
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
  symbol.value.trim().replace(/^(sh|sz|bj)/i, '').toUpperCase()
)

const symbolHint = computed(() => {
  const code = normalizedSymbol.value
  if (!/^\d{6}$/.test(code)) return ''
  const m = detectMarket(code)
  if (!m) return ''
  const marker = '.' + m
  const hit = suggestions.value.find((s) => s.code === code)
  return hit ? `${marker}  ${hit.name}` : marker
})

const investDayOptions = computed(() => {
  if (frequency.value === 'weekly') {
    return ['周一', '周二', '周三', '周四', '周五', '周六', '周日'].map((n, i) => ({
      label: n,
      value: i,
    }))
  }
  return Array.from({ length: 28 }, (_, i) => ({ label: `每月 ${i + 1} 日`, value: i + 1 }))
})

function onFrequencyChange() {
  if (frequency.value === 'weekly') {
    if (investDay.value > 6) investDay.value = 2
  } else {
    if (investDay.value < 1 || investDay.value > 28) investDay.value = 15
  }
}

async function runBacktest() {
  errorMsg.value = ''
  chartData.value = null
  summary.value = null

  const code = normalizedSymbol.value
  if (!code) {
    errorMsg.value = '请填写有效的标的代码'
    return
  }
  if (!amount.value || amount.value < 100) {
    errorMsg.value = '每期金额需 ≥ 100'
    return
  }
  if (startDate.value >= endDate.value) {
    errorMsg.value = '起始日期需早于结束日期'
    return
  }

  loading.value = true
  try {
    const r = await createBacktest({
      symbol: code,
      frequency: frequency.value,
      amount: amount.value,
      start_date: startDate.value,
      end_date: endDate.value,
      invest_day: investDay.value,
      mode: mode.value,
      ma_period: maPeriod.value,
    })
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    const taskId = r.data.task_id
    const [c, s] = await Promise.all([getChart(taskId), getSummary(taskId)])
    if (c.code === 0) chartData.value = c.data
    if (s.code === 0) summary.value = s.data
    if (c.code !== 0) errorMsg.value = c.message
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

// 图表标题：标的名称 · 回测结果（无名称时回退为代码）
const chartTitle = computed(() => {
  const code = normalizedSymbol.value || symbol.value.trim()
  const name = chartData.value?.symbol_name
  const modeTag = mode.value === 'smart' ? '（智能定投）' : '（普通定投）'
  return `${name || code} · 回测结果${modeTag}`
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
    <h1>定投回测</h1>

    <!-- 参数表单 -->
    <div class="form-card">
      <div class="form-row">
        <label class="symbol-label">
          标的代码
          <div class="symbol-field">
            <input
              v-model="symbol"
              list="symbol-suggestions"
              placeholder="如 000001 / SZ000001"
              @input="onSymbolInput"
            />
            <span v-if="symbolHint" class="symbol-hint">{{ symbolHint }}</span>
          </div>
          <datalist id="symbol-suggestions">
            <option v-for="s in suggestions" :key="s.code" :value="s.code">{{ s.name }}</option>
          </datalist>
        </label>

        <label>
          定投频率
          <select v-model="frequency" @change="onFrequencyChange">
            <option value="weekly">每周</option>
            <option value="monthly">每月</option>
          </select>
        </label>

        <label>
          投资日
          <select v-model.number="investDay">
            <option v-for="o in investDayOptions" :key="o.value" :value="o.value">{{ o.label }}</option>
          </select>
        </label>

        <label>
          定投模式
          <select v-model="mode">
            <option value="normal">普通定投</option>
            <option value="smart">智能定投</option>
          </select>
        </label>
        <label v-if="mode === 'smart'">
          均线周期
          <input v-model.number="maPeriod" type="number" min="2" max="1000" step="1" />
        </label>
        <div v-if="mode === 'smart'" class="smart-hint">
          <span>偏离度 X = (T-1 收盘 − MA{{ maPeriod }}) / MA{{ maPeriod }}</span>
          <span class="info-icon" tabindex="0" aria-label="各档扣款率">
            !<span class="info-pop">
              <div class="rate-cols">
                <table>
                  <thead><tr><th>偏离度（高位）</th><th>扣款率</th></tr></thead>
                  <tbody>
                    <tr v-for="(b, i) in highBands" :key="'h' + i"><td>{{ b[0] }}</td><td>{{ b[1] }}</td></tr>
                  </tbody>
                </table>
                <table>
                  <thead><tr><th>偏离度（低位）</th><th>扣款率</th></tr></thead>
                  <tbody>
                    <tr v-for="(b, i) in lowBands" :key="'l' + i"><td>{{ b[0] }}</td><td>{{ b[1] }}</td></tr>
                  </tbody>
                </table>
              </div>
            </span>
          </span>
        </div>
      </div>

      <div class="form-row">
        <label>
          每期金额（元）
          <input v-model.number="amount" type="number" min="100" step="100" />
        </label>
        <label>
          起始日期
          <input v-model="startDate" type="date" />
        </label>
        <label>
          结束日期
          <input v-model="endDate" type="date" />
        </label>
        <button :disabled="loading" class="primary" @click="runBacktest">
          {{ loading ? '回测中…' : '开始回测' }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

    <!-- 指标卡片 -->
    <div v-if="summary" class="cards">
      <MetricCard label="定投期数" :value="String(summary.invest_count)" />
      <MetricCard label="累计投入" :value="fmt(summary.total_invested)" />
      <MetricCard label="当前市值" :value="fmt(summary.final_value)" />
      <MetricCard label="累计收益" :value="fmt(summary.total_pnl)" :color="pnlColor(summary.total_pnl)" />
      <MetricCard label="累计收益率" :value="fmt(summary.total_return_rate) + '%'" :color="pnlColor(summary.total_return_rate)" />
      <MetricCard label="年化收益率" :value="fmt(summary.annualized_return) + '%'" :color="pnlColor(summary.annualized_return)" />
      <MetricCard label="最大回撤" :value="fmt(summary.max_drawdown) + '%'" :color="COLOR_DOWN" />
    </div>

    <!-- 图表 -->
    <div v-if="chartData" class="chart-card">
      <h3>{{ chartTitle }}</h3>
      <DcaChart :data="chartData" />
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
.smart-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  align-self: flex-end;
  margin: 0 0 9px 4px;
}
.info-icon {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  cursor: help;
  user-select: none;
}
.info-pop {
  position: absolute;
  left: 22px;
  top: -10px;
  z-index: 50;
  display: none;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.18);
  white-space: nowrap;
}
.info-icon:hover .info-pop,
.info-icon:focus .info-pop {
  display: block;
}
.rate-cols {
  display: flex;
  gap: 32px;
  flex-wrap: wrap;
}
.rate-cols table {
  border-collapse: collapse;
  font-size: 12px;
}
.rate-cols th,
.rate-cols td {
  padding: 3px 12px 3px 0;
  text-align: left;
  color: var(--text-secondary);
}
.rate-cols th {
  font-weight: 600;
  color: var(--text);
}
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 16px 0;
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
.err {
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
