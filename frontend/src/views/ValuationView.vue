<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import MetricCard from '../components/MetricCard.vue'
import { getValuation, type ValuationData } from '../api'

const INDICES: { code: string; name: string }[] = [
  { code: '000300', name: '沪深300' },
  { code: '000905', name: '中证500' },
  { code: '000852', name: '中证1000' },
  { code: '000016', name: '上证50' },
  { code: '399006', name: '创业板指' },
]

const symbol = ref('000300')
const data = ref<ValuationData | null>(null)
const loading = ref(false)
const errorMsg = ref('')

const gaugeEl = ref<HTMLDivElement | null>(null)
const histEl = ref<HTMLDivElement | null>(null)
let gauge: echarts.ECharts | null = null
let hist: echarts.ECharts | null = null

// 分位→温度档（红=贵，绿=便宜，A 股配色红涨绿跌此处用于"热度"）
function tempColor(p: number): string {
  if (p >= 80) return '#ee6666'
  if (p >= 60) return '#faad14'
  if (p >= 40) return '#8a8f99'
  return '#3ba272'
}
const tempLabel = (p: number) => (p >= 80 ? '偏贵' : p >= 60 ? '中高' : p >= 40 ? '中性' : '偏便宜')

async function load() {
  loading.value = true
  errorMsg.value = ''
  data.value = null
  try {
    const r = await getValuation(symbol.value)
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    data.value = r.data
    await nextTick()
    render()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function render() {
  const d = data.value
  if (!d?.available) return
  const p = d.percentile ?? 0

  if (gaugeEl.value) {
    if (!gauge) gauge = echarts.init(gaugeEl.value)
    gauge.setOption(
      {
        series: [
          {
            type: 'gauge',
            min: 0,
            max: 100,
            startAngle: 200,
            endAngle: -20,
            progress: { show: true, width: 14, itemStyle: { color: tempColor(p) } },
            axisLine: { lineStyle: { width: 14, color: [[0.4, '#3ba272'], [0.6, '#8a8f99'], [0.8, '#faad14'], [1, '#ee6666']] } },
            pointer: { width: 5, length: '65%' },
            detail: {
              valueAnimation: true,
              formatter: `{value}%\n{n|${tempLabel(p)}}`,
              fontSize: 22,
              offsetCenter: [0, '32%'],
              rich: { n: { fontSize: 13, color: '#888' } },
            },
            title: { show: false },
            data: [{ value: p, name: '历史分位' }],
          },
        ],
      } as echarts.EChartsOption,
      true,
    )
  }

  if (histEl.value && d.series) {
    if (!hist) hist = echarts.init(histEl.value)
    const dates = d.series.map((s) => s[0])
    const pes = d.series.map((s) => s[1])
    hist.setOption(
      {
        tooltip: { trigger: 'axis' },
        grid: { left: 56, right: 56, top: 40, bottom: 36 },
        xAxis: { type: 'category', data: dates, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', name: 'PE', nameLocation: 'end', nameGap: 8, axisLabel: { fontSize: 10 } },
        dataZoom: [{ type: 'inside' }],
        series: [
          {
            type: 'line',
            data: pes,
            symbol: 'none',
            lineStyle: { color: '#1f6feb', width: 1.5 },
            areaStyle: { opacity: 0.08 },
            markLine: {
              symbol: 'none',
              data: [
                { yAxis: d.current_pe ?? 0, lineStyle: { color: '#ee6666', type: 'dashed' }, label: { formatter: '当前', color: '#ee6666', position: 'insideEndTop' } },
              ],
            },
          },
        ],
      } as echarts.EChartsOption,
      true,
    )
  }
}

watch(symbol, load)
const resize = () => {
  gauge?.resize()
  hist?.resize()
}
onMounted(() => {
  load()
  window.addEventListener('resize', resize)
})
onUnmounted(() => {
  window.removeEventListener('resize', resize)
  gauge?.dispose()
  hist?.dispose()
})
</script>

<template>
  <section>
    <h1>估值温度计</h1>
    <p class="muted">指数 PE 历史分位：回答「现在贵不贵」。分位越高越偏贵（红），越低越偏便宜（绿）。</p>

    <div class="form-card">
      <label>
        指数
        <select v-model="symbol">
          <option v-for="i in INDICES" :key="i.code" :value="i.code">{{ i.name }}（{{ i.code }}）</option>
        </select>
      </label>
      <button :disabled="loading" class="primary" @click="load">
        {{ loading ? '加载中…' : '查询' }}
      </button>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <p v-else-if="data && !data.available" class="err">{{ data.reason }}</p>

    <template v-if="data?.available">
      <div class="cards">
        <MetricCard label="当前 PE" :value="String(data.current_pe)" />
        <MetricCard label="历史分位" :value="(data.percentile ?? 0) + '%  ' + tempLabel(data.percentile ?? 0)" :color="tempColor(data.percentile ?? 0)" />
        <MetricCard label="历史最低" :value="String(data.min)" />
        <MetricCard label="历史最高" :value="String(data.max)" />
      </div>
      <div class="chart-row">
        <div ref="gaugeEl" class="gauge"></div>
        <div ref="histEl" class="hist"></div>
      </div>
      <p class="muted">数据截至 {{ data.as_of }} · 来源：乐咕乐股（stock_index_pe_lg）</p>
    </template>
  </section>
</template>

<style scoped>
.muted {
  color: var(--text-tertiary);
  font-size: 13px;
}
.form-card {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 16px 20px;
  background: var(--surface);
  margin: 16px 0;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 13px;
  color: var(--text-secondary);
  gap: 4px;
}
select {
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  font-size: 14px;
  min-width: 200px;
  background: var(--input-bg);
  color: var(--text);
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
.chart-row {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.gauge {
  width: 320px;
  height: 280px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface);
}
.hist {
  flex: 1;
  min-width: 360px;
  height: 280px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--surface);
}
.err {
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
