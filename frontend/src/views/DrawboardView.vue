<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import MetricCard from '../components/MetricCard.vue'
import DrawboardChart from '../components/DrawboardChart.vue'
import {
  getDrawboardChart,
  getDrawboardSummary,
  runDrawdownBacktest,
  saveDrawboard,
  searchSymbols,
  type DrawboardChartData,
  type DrawSellMode,
  type DrawSummary,
  type SymbolItem,
} from '../api'
import { parseDrawboardTaskId } from '../utils/taskId'

const route = useRoute()

// A 股配色惯例：红涨绿跌
const COLOR_UP = '#ee6666'
const COLOR_DOWN = '#3ba272'

// 近 3 年起始日（前端算，后端不强制）
function yearsAgo(n: number): string {
  const d = new Date()
  d.setFullYear(d.getFullYear() - n)
  return d.toISOString().slice(0, 10)
}

const symbol = ref('510880')
const startDate = ref(yearsAgo(3))
const endDate = ref(new Date().toISOString().slice(0, 10))
const sellMode = ref<DrawSellMode>('new_high')
const buyAmount = ref(10000)
const addAmount = ref(5000)
const threshold = ref(20)
const step = ref(5)
const showAdvanced = ref(false)

const loading = ref(false)
const saving = ref(false)
const errorMsg = ref('')
const savedMsg = ref('')
const chartData = ref<DrawboardChartData | null>(null)
const summary = ref<DrawSummary | null>(null)

const SELL_LABEL: Record<DrawSellMode, string> = {
  none: '只买不卖',
  new_high: '新高清仓',
  partial: '半仓兑现',
}
const sellHint = computed(
  () =>
    ({
      none: '只买不卖，持仓展示收益率',
      new_high: '新高（回撤归 0）清仓兑现',
      partial: '新高卖出 50%，留底仓等下次跌破再买',
    })[sellMode.value],
)

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
  if (!buyAmount.value || buyAmount.value <= 0) return '首笔金额需 > 0'
  if (!addAmount.value || addAmount.value <= 0) return '加仓金额需 > 0'
  if (!threshold.value || threshold.value <= 0) return '回撤阈值需 > 0'
  if (!step.value || step.value <= 0) return '加仓步长需 > 0'
  if (startDate.value >= endDate.value) return '起始日期需早于结束日期'
  return ''
}

// 实时重算（GET /backtest，不落库）——「开始回测」按钮触发
async function runBacktest() {
  errorMsg.value = ''
  const err = validate()
  if (err) {
    errorMsg.value = err
    return
  }
  loading.value = true
  chartData.value = null
  summary.value = null
  try {
    const r = await runDrawdownBacktest({
      symbol: normalizedSymbol.value,
      start: startDate.value,
      end: endDate.value,
      threshold: threshold.value,
      step: step.value,
      buy_amount: buyAmount.value,
      add_amount: addAmount.value,
      sell_mode: sellMode.value,
    })
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    // DrawBacktestResult = 图表数据 + summary；拆给组件与卡片
    summary.value = r.data.summary
    chartData.value = r.data
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

// 保存落库（POST /save）——「保存」按钮触发，返回 task_id 供首页/直达消费
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
    const r = await saveDrawboard({
      symbol: normalizedSymbol.value,
      start_date: startDate.value,
      end_date: endDate.value,
      threshold: threshold.value,
      step: step.value,
      buy_amount: buyAmount.value,
      add_amount: addAmount.value,
      sell_mode: sellMode.value,
    })
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
    const parsed = parseDrawboardTaskId(taskId)
    if (parsed) {
      symbol.value = parsed.symbol
      startDate.value = parsed.startDate
      endDate.value = parsed.endDate
      threshold.value = parsed.threshold
      step.value = parsed.step
      buyAmount.value = parsed.buyAmount
      addAmount.value = parsed.addAmount
      sellMode.value = parsed.sellMode
    }
    const [c, s] = await Promise.all([getDrawboardChart(taskId), getDrawboardSummary(taskId)])
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
})

const chartTitle = computed(() => {
  const code = normalizedSymbol.value || symbol.value.trim()
  const name = chartData.value?.symbol_name
  return `${name || code} · 回撤买入策略回测（${SELL_LABEL[sellMode.value]}）`
})

function fmt(n: number | undefined | null, d = 2): string {
  if (n == null || Number.isNaN(n)) return '-'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d })
}
function pnlColor(n: number | undefined | null): string {
  if (n == null) return ''
  return n >= 0 ? COLOR_UP : COLOR_DOWN
}
</script>

<template>
  <section>
    <h1>回撤买入策略看板</h1>

    <!-- 参数表单（克隆 MA120：.form-card + 两行 .form-row + 折叠高级区 + button.primary） -->
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
          卖出方式
          <select v-model="sellMode">
            <option value="new_high">新高清仓</option>
            <option value="none">只买不卖</option>
            <option value="partial">半仓兑现</option>
          </select>
        </label>

        <label>
          首笔金额（元）
          <input v-model.number="buyAmount" type="number" min="100" step="100" />
        </label>
        <label>
          加仓金额（元）
          <input v-model.number="addAmount" type="number" min="100" step="100" />
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
          回撤阈值 %
          <input v-model.number="threshold" type="number" min="1" max="80" step="1" />
        </label>
        <label>
          加仓步长 %
          <input v-model.number="step" type="number" min="1" max="20" step="1" class="narrow" />
        </label>
        <button :disabled="loading" class="primary" @click="runBacktest">
          {{ loading ? '回测中…' : '开始回测' }}
        </button>
        <button :disabled="saving" class="primary" @click="save">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </div>

      <!-- 高级参数（预留，本任务暂无可折叠项） -->
      <div class="advanced">
        <button class="advanced-toggle" type="button" @click="showAdvanced = !showAdvanced">
          {{ showAdvanced ? '▾' : '▸' }} 高级参数
        </button>
        <div v-if="showAdvanced" class="form-row advanced-row">
          <p class="muted">暂无可折叠的高级参数；回撤阈值 / 加仓步长已置于主表单。</p>
        </div>
      </div>
    </div>

    <p class="muted hint-line">卖出方式：{{ sellHint }}</p>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <p v-if="savedMsg" class="ok">{{ savedMsg }}</p>

    <!-- 指标卡片（克隆 MA120，含「买卖次数」合并卡） -->
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
      <div class="trade-card">
        <div class="tc-label">买卖次数</div>
        <div class="trade-value">
          <span class="num-buy">{{ summary.buy_count }}</span>
          <span class="sep">/</span>
          <span class="num-sell">{{ summary.sell_count }}</span>
        </div>
      </div>
    </div>

    <!-- 图表（独立组件，结构与 Ma120Chart 一致） -->
    <div v-if="chartData" class="chart-card">
      <h3>{{ chartTitle }}</h3>
      <DrawboardChart :data="chartData" :threshold="threshold" />
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
.muted {
  color: var(--text-tertiary);
  font-size: 13px;
  margin: 0;
}
.hint-line {
  margin: 0 0 12px;
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
  align-items: flex-end; /* 下边缘对齐 */
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
  color: #ee6666; /* 买入红，与图表买入标记一致 */
}
.num-sell {
  color: #3a7afe; /* 卖出蓝，与图表卖出标记一致 */
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
.err {
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 6px;
  padding: 8px 12px;
}
.ok {
  color: #2f8a5f;
  background: color-mix(in srgb, #3ba272 14%, transparent);
  border: 1px solid color-mix(in srgb, #3ba272 30%, transparent);
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
