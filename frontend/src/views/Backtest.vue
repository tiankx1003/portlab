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

const symbol = ref('000001')
const frequency = ref<'weekly' | 'monthly'>('weekly')
const investDay = ref(2)
const amount = ref(1000)
const startDate = ref('2024-01-01')
const endDate = ref(new Date().toISOString().slice(0, 10))

const loading = ref(false)
const errorMsg = ref('')
const chartData = ref<ChartData | null>(null)
const summary = ref<SummaryData | null>(null)

// 标的搜索（带去抖）
const suggestions = ref<SymbolItem[]>([])
let debounce: ReturnType<typeof setTimeout> | undefined
function onSymbolInput() {
  clearTimeout(debounce)
  const q = symbol.value.trim()
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

  if (!symbol.value.trim()) {
    errorMsg.value = '请填写标的代码'
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
      symbol: symbol.value.trim(),
      frequency: frequency.value,
      amount: amount.value,
      start_date: startDate.value,
      end_date: endDate.value,
      invest_day: investDay.value,
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

function fmt(n: number | undefined, d = 2): string {
  if (n == null || Number.isNaN(n)) return '-'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d })
}
function pnlColor(n: number | undefined): string {
  if (n == null) return ''
  return n >= 0 ? '#3ba272' : '#ee6666'
}
</script>

<template>
  <section>
    <h1>定投回测</h1>

    <!-- 参数表单 -->
    <div class="form-card">
      <div class="form-row">
        <label>
          标的代码
          <input
            v-model="symbol"
            list="symbol-suggestions"
            placeholder="如 000001（可搜索）"
            @input="onSymbolInput"
          />
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
      <MetricCard label="累计投入" :value="fmt(summary.total_invested)" />
      <MetricCard label="当前市值" :value="fmt(summary.final_value)" />
      <MetricCard label="累计收益" :value="fmt(summary.total_pnl)" :color="pnlColor(summary.total_pnl)" />
      <MetricCard label="累计收益率" :value="fmt(summary.total_return_rate) + '%'" :color="pnlColor(summary.total_return_rate)" />
      <MetricCard label="年化收益率" :value="fmt(summary.annualized_return) + '%'" :color="pnlColor(summary.annualized_return)" />
      <MetricCard label="最大回撤" :value="fmt(summary.max_drawdown) + '%'" color="#ee6666" />
      <MetricCard label="定投期数" :value="String(summary.invest_count)" hint="期" />
    </div>

    <!-- 图表 -->
    <div v-if="chartData" class="chart-card">
      <h3>回测结果</h3>
      <DcaChart :data="chartData" />
    </div>
  </section>
</template>

<style scoped>
.form-card {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 16px 20px;
  background: #fff;
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
  color: #4e5969;
  gap: 4px;
}
input,
select {
  padding: 8px 10px;
  border: 1px solid #d9d9d9;
  border-radius: 6px;
  font-size: 14px;
  min-width: 150px;
}
button.primary {
  background: #1f6feb;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 9px 22px;
  font-size: 14px;
  cursor: pointer;
  height: 38px;
}
button.primary:disabled {
  background: #9aa4b2;
  cursor: not-allowed;
}
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 16px 0;
}
.chart-card {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 16px 20px;
  background: #fff;
}
.err {
  color: #d4380d;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
