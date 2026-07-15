<script setup lang="ts">
import { computed, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import Ma120Chart from '../components/Ma120Chart.vue'
import {
  createMa120,
  getMa120Chart,
  getMa120Summary,
  searchSymbols,
  type CapitalMode,
  type DividendMode,
  type Ma120ChartData,
  type Ma120SummaryData,
  type SellMode,
  type SymbolItem,
} from '../api'

// A 股配色惯例：红涨绿跌
const COLOR_UP = '#ee6666'
const COLOR_DOWN = '#3ba272'

const symbol = ref('510880')
const startDate = ref('2022-01-01')
const endDate = ref(new Date().toISOString().slice(0, 10))
const capitalMode = ref<CapitalMode>('fixed')
const principal = ref(100000)
const monthlyAmount = ref(2000)
const splits = ref(10)
const maPeriod = ref(120)
const buyThreshold = ref(0.985)
const step = ref(0.01)
const crashThreshold = ref(0.05)
const crashMultiplier = ref(2)
const sellMode = ref<SellMode>('batch')
const dividendMode = ref<DividendMode>('cash')
const showAdvanced = ref(false)

const loading = ref(false)
const errorMsg = ref('')
const chartData = ref<Ma120ChartData | null>(null)
const summary = ref<Ma120SummaryData | null>(null)

const showPrincipal = computed(() => capitalMode.value !== 'recurring')
const showMonthly = computed(() => capitalMode.value !== 'fixed')

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

async function runBacktest() {
  errorMsg.value = ''
  chartData.value = null
  summary.value = null

  const code = normalizedSymbol.value
  if (!code) {
    errorMsg.value = '请填写有效的标的代码'
    return
  }
  if (showPrincipal.value && (!principal.value || principal.value <= 0)) {
    errorMsg.value = '初始本金需 > 0'
    return
  }
  if (showMonthly.value && (!monthlyAmount.value || monthlyAmount.value <= 0)) {
    errorMsg.value = '每月投入需 > 0'
    return
  }
  if (startDate.value >= endDate.value) {
    errorMsg.value = '起始日期需早于结束日期'
    return
  }

  loading.value = true
  try {
    const r = await createMa120({
      symbol: code,
      start_date: startDate.value,
      end_date: endDate.value,
      capital_mode: capitalMode.value,
      principal: showPrincipal.value ? principal.value : null,
      monthly_amount: showMonthly.value ? monthlyAmount.value : null,
      splits: splits.value,
      ma_period: maPeriod.value,
      buy_threshold: buyThreshold.value,
      step: step.value,
      crash_threshold: crashThreshold.value,
      crash_multiplier: crashMultiplier.value,
      sell_mode: sellMode.value,
      dividend_mode: dividendMode.value,
    })
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    const taskId = r.data.task_id
    const [c, s] = await Promise.all([getMa120Chart(taskId), getMa120Summary(taskId)])
    if (c.code === 0) chartData.value = c.data
    if (s.code === 0) summary.value = s.data
    if (c.code !== 0) errorMsg.value = c.message
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

const chartTitle = computed(() => {
  const code = normalizedSymbol.value || symbol.value.trim()
  const name = chartData.value?.symbol_name
  const modeTag = {
    fixed: '（固定本金）',
    recurring: '（每月投入）',
    hybrid: '（混合）',
  }[capitalMode.value]
  return `${name || code} · MA120 策略回测${modeTag}`
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
    <h1>MA120 策略回测</h1>

    <!-- 参数表单 -->
    <div class="form-card">
      <div class="form-row">
        <label class="symbol-label">
          标的代码
          <div class="symbol-field">
            <input
              v-model="symbol"
              list="symbol-suggestions"
              placeholder="如 510880 / 510300"
              @input="onSymbolInput"
            />
            <span v-if="symbolHint" class="symbol-hint">{{ symbolHint }}</span>
          </div>
          <datalist id="symbol-suggestions">
            <option v-for="s in suggestions" :key="s.code" :value="s.code">{{ s.name }}</option>
          </datalist>
        </label>

        <label>
          资金模式
          <select v-model="capitalMode">
            <option value="fixed">固定本金</option>
            <option value="recurring">每月投入</option>
            <option value="hybrid">混合</option>
          </select>
        </label>

        <label v-if="showPrincipal">
          初始本金（元）
          <input v-model.number="principal" type="number" min="1" step="1000" />
        </label>
        <label v-if="showMonthly">
          每月投入（元）
          <input v-model.number="monthlyAmount" type="number" min="1" step="100" />
        </label>
      </div>

      <div class="form-row">
        <label>
          起始日期
          <input v-model="startDate" type="date" />
        </label>
        <label>
          结束日期
          <input v-model="endDate" type="date" />
        </label>
        <label>
          份数
          <input v-model.number="splits" type="number" min="1" step="1" />
        </label>
        <label>
          MA 周期
          <input v-model.number="maPeriod" type="number" min="2" max="1000" step="1" />
        </label>
        <label>
          卖出方式
          <select v-model="sellMode">
            <option value="batch">分批</option>
            <option value="all">全部</option>
            <option value="half">半仓</option>
          </select>
        </label>
        <label>
          分红处理
          <select v-model="dividendMode">
            <option value="cash">现金</option>
            <option value="reinvest" disabled>复投（待实现）</option>
          </select>
        </label>
      </div>

      <!-- 高级参数（可折叠） -->
      <div class="advanced">
        <button class="advanced-toggle" type="button" @click="showAdvanced = !showAdvanced">
          {{ showAdvanced ? '▾' : '▸' }} 高级参数
        </button>
        <div v-if="showAdvanced" class="form-row advanced-row">
          <label>
            买入阈值
            <input v-model.number="buyThreshold" type="number" min="0.5" max="1.5" step="0.005" />
          </label>
          <label>
            加仓步长
            <input v-model.number="step" type="number" min="0.001" max="0.1" step="0.005" />
          </label>
          <label>
            暴跌阈值
            <input v-model.number="crashThreshold" type="number" min="0.01" max="0.5" step="0.01" />
          </label>
          <label>
            暴跌加倍倍数
            <input v-model.number="crashMultiplier" type="number" min="1" max="10" step="1" />
          </label>
        </div>
      </div>

      <div class="form-row">
        <button :disabled="loading" class="primary" @click="runBacktest">
          {{ loading ? '回测中…' : '开始回测' }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

    <!-- 指标卡片 -->
    <div v-if="summary" class="cards">
      <MetricCard label="累计投入" :value="fmt(summary.total_invested)" />
      <MetricCard label="当前市值" :value="fmt(summary.final_value)" />
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
      <MetricCard label="买入次数" :value="String(summary.buy_count)" />
      <MetricCard label="卖出次数" :value="String(summary.sell_count)" />
      <MetricCard label="分红累计" :value="fmt(summary.dividend_total)" />
      <MetricCard label="胜率" :value="fmt(summary.win_rate) + '%'" />
    </div>

    <!-- 图表 -->
    <div v-if="chartData" class="chart-card">
      <h3>{{ chartTitle }}</h3>
      <Ma120Chart :data="chartData" />
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
.advanced {
  margin-bottom: 12px;
}
.advanced-toggle {
  background: none;
  border: none;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 0;
}
.advanced-toggle:hover {
  color: var(--primary);
}
.advanced-row {
  margin-top: 10px;
  margin-bottom: 0;
  padding-top: 10px;
  border-top: 1px dashed var(--border-light);
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
