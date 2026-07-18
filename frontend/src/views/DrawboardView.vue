<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import MetricCard from '../components/MetricCard.vue'
import {
  getDrawdownSeries,
  runDrawdownBacktest,
  type DrawBacktestResult,
  type DrawdownSeries,
} from '../api'

// A 股配色：红涨绿跌
const C_PRICE = '#ee6666' // 价格/收益（红）
const C_DD = '#3ba272' // 回撤（绿）
const C_BENCH = '#8a8f99' // 基准（灰）
const C_MV = '#1f6feb' // 市值（蓝）
const C_BUY = '#ee6666'
const C_SELL = '#3ba272'

const symbol = ref('512890')
const startDate = ref('2022-01-01')
const endDate = ref(new Date().toISOString().slice(0, 10))
const threshold = ref(20)
const step = ref(5)
const buyAmount = ref(10000)
const addAmount = ref(10000)

const loading = ref(false)
const errorMsg = ref('')
const series = ref<DrawdownSeries | null>(null)
const result = ref<DrawBacktestResult | null>(null)

const el = ref<HTMLDivElement | null>(null)
let chart: echarts.ECharts | null = null
let resizeObs: ResizeObserver | null = null

const summary = computed(() => result.value?.summary ?? null)

function fmt(n: number | undefined | null, d = 2): string {
  if (n == null || Number.isNaN(n)) return '-'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d })
}

async function loadSeries() {
  loading.value = true
  errorMsg.value = ''
  series.value = null
  result.value = null
  try {
    const r = await getDrawdownSeries(symbol.value, startDate.value, endDate.value)
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    series.value = r.data
    await runBacktest()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

async function runBacktest() {
  if (!series.value?.dates.length) return
  try {
    const r = await runDrawdownBacktest({
      symbol: symbol.value,
      start: startDate.value,
      end: endDate.value,
      threshold: threshold.value,
      step: step.value,
      buy_amount: buyAmount.value,
      add_amount: addAmount.value,
    })
    if (r.code === 0) result.value = r.data
  } catch {
    /* 忽略，series 仍可看 */
  }
}

function buildOption(): echarts.EChartsOption {
  const s = series.value
  if (!s) return {}
  // 基准按日对齐（同为日线交易日，长度一致才叠加，避免错位）
  const benchAligned =
    s.benchmark_pct.length === s.dates.length ? s.benchmark_pct : s.dates.map(() => null)
  const r = result.value
  const retAligned = r && r.dates.length === s.dates.length ? r.return_rates : s.dates.map(() => null)
  const mvAligned = r && r.dates.length === s.dates.length ? r.market_values : s.dates.map(() => null)

  // 买/卖 markPoint：用 date → price_pct 定位
  const ppByDate = new Map<string, number | null>()
  s.dates.forEach((d, i) => ppByDate.set(d, s.price_pct[i]))
  const mkPoint = (pts: { date: string; price: number; amount: number }[], color: string) =>
    pts.map((p) => ({
      coord: [p.date, ppByDate.get(p.date) ?? 0],
      value: color === C_BUY ? '买' : '卖',
      itemStyle: { color },
    }))

  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'cross' } },
    legend: { data: ['价格%', '回撤%', '基准%', '策略收益%', '市值(元)'], top: 0 },
    grid: { left: 56, right: 64, top: 40, bottom: 60 },
    xAxis: { type: 'category', data: s.dates, axisLabel: { fontSize: 10 } },
    yAxis: [
      {
        type: 'value',
        name: '%',
        position: 'left',
        axisLine: { lineStyle: { color: C_PRICE } },
      },
      { type: 'value', name: '市值', position: 'right', axisLine: { lineStyle: { color: C_MV } } },
    ],
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 18, bottom: 8 }],
    series: ([
      {
        name: '价格%', type: 'line', data: s.price_pct, yAxisIndex: 0, smooth: true,
        symbol: 'none', lineStyle: { color: C_PRICE, width: 2 },
        markPoint: {
          symbol: 'pin', symbolSize: 38,
          data: [...(r ? mkPoint(r.buy_points, C_BUY) : []), ...(r ? mkPoint(r.sell_points, C_SELL) : [])],
        },
        markLine: {
          symbol: 'none',
          lineStyle: { color: C_DD, type: 'dashed', width: 1.5 },
          label: { formatter: `阈值 -${threshold.value}%`, position: 'insideEndTop', color: C_DD },
          data: [{ yAxis: -threshold.value }],
        },
      },
      {
        name: '回撤%', type: 'line', data: s.drawdown, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: C_DD, width: 1.2 }, areaStyle: { opacity: 0.08 },
      },
      {
        name: '基准%', type: 'line', data: benchAligned, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: C_BENCH, width: 1, type: 'dashed' },
      },
      {
        name: '策略收益%', type: 'line', data: retAligned, yAxisIndex: 0, symbol: 'none',
        lineStyle: { color: '#faad14', width: 1.2 },
      },
      {
        name: '市值(元)', type: 'line', data: mvAligned, yAxisIndex: 1, symbol: 'none',
        lineStyle: { color: C_MV, width: 1.5 },
      },
    ] as any[]),
  }
}

function render() {
  if (!chart) return
  chart.setOption(buildOption(), true)
}

// 阈值/步长/金额变化（slider 松手 @change）→ 重算
watch([threshold, step, buyAmount, addAmount], () => {
  if (series.value) runBacktest().then(render)
})
watch([series, result], () => nextTick(render), { deep: true })

const resize = () => chart?.resize()
onMounted(() => {
  if (el.value) chart = echarts.init(el.value)
  resizeObs = new ResizeObserver(resize)
  if (el.value) resizeObs.observe(el.value)
  loadSeries()
})
onUnmounted(() => {
  resizeObs?.disconnect()
  chart?.dispose()
  chart = null
})
</script>

<template>
  <section>
    <h1>回撤买入策略看板</h1>
    <p class="muted">
      拖动「回撤阈值」调整买入条件：价格滚动回撤达阈值首买，每再多跌 {{ step }}% 加仓，新高（回撤归 0）清仓兑现。
    </p>

    <div class="form-card">
      <div class="form-row">
        <label>
          标的代码
          <input v-model="symbol" />
        </label>
        <label>
          起始日期
          <input v-model="startDate" type="date" />
        </label>
        <label>
          结束日期
          <input v-model="endDate" type="date" />
        </label>
        <button :disabled="loading" class="primary" @click="loadSeries">
          {{ loading ? '加载中…' : '加载行情' }}
        </button>
      </div>
      <div class="form-row">
        <label class="slider-label">
          回撤阈值：{{ threshold }}%
          <input v-model.number="threshold" type="range" min="3" max="50" step="1" />
        </label>
        <label>
          加仓步长 %
          <input v-model.number="step" type="number" min="1" max="20" step="1" />
        </label>
        <label>
          首买金额
          <input v-model.number="buyAmount" type="number" min="100" step="100" />
        </label>
        <label>
          加仓金额
          <input v-model.number="addAmount" type="number" min="100" step="100" />
        </label>
      </div>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

    <div v-if="summary" class="cards">
      <MetricCard label="买入次数" :value="String(summary.buy_count)" />
      <MetricCard label="卖出次数" :value="String(summary.sell_count)" />
      <MetricCard label="累计投入" :value="fmt(summary.total_invested)" />
      <MetricCard label="最终市值" :value="fmt(summary.final_value)" />
      <MetricCard
        label="累计收益"
        :value="fmt(summary.total_pnl)"
        :color="summary.total_pnl >= 0 ? C_PRICE : C_DD"
      />
      <MetricCard
        label="累计收益率"
        :value="fmt(summary.total_return_rate) + '%'"
        :color="summary.total_return_rate >= 0 ? C_PRICE : C_DD"
      />
    </div>

    <div class="chart-card">
      <div ref="el" class="chart"></div>
    </div>
  </section>
</template>

<style scoped>
.muted {
  color: var(--text-tertiary);
  font-size: 13px;
  margin: 4px 0 0;
}
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
.slider-label {
  min-width: 240px;
}
input[type='date'],
input:not([type]) {
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  font-size: 14px;
  min-width: 140px;
  background: var(--input-bg);
  color: var(--text);
}
input[type='number'] {
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  font-size: 14px;
  min-width: 110px;
  background: var(--input-bg);
  color: var(--text);
}
input[type='range'] {
  width: 100%;
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
.chart-card {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px;
  background: var(--surface);
}
.chart {
  width: 100%;
  height: 520px;
}
.err {
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
