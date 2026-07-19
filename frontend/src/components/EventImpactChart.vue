<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { EventImpactData } from '../api'
import { theme } from '../composables/useTheme'

// A 股配色惯例：红涨绿跌
const COLOR_UP = '#ee6666'
const COLOR_DOWN = '#3ba272'
const COLOR_BENCH = '#9b6bff'
const COLOR_EVENT = '#fa8c16'
// 多曲线分类色板
const PALETTE = ['#5470c6', '#ee6666', '#3ba272', '#fac858', '#ee9c2a', '#73c0de', '#fc8452', '#9a60b4']

const props = defineProps<{ data: EventImpactData | null }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function themeColors() {
  const dark = theme.value === 'dark'
  return {
    axisLine: dark ? '#3a3a42' : '#c9cdd4',
    axisLabel: dark ? '#a0a0a8' : '#6e7079',
    splitLine: dark ? '#2a2a30' : '#e5e6eb',
    tooltipBg: dark ? '#2a2a30' : '#ffffff',
    tooltipBorder: dark ? '#3a3a42' : '#dddddd',
    tooltipText: dark ? '#e8e8ec' : '#333333',
  }
}

function buildOption(d: EventImpactData): echarts.EChartsOption {
  const tc = themeColors()
  // 日期并集（升序）
  const dateSet = new Set<string>()
  Object.values(d.window_returns).forEach((s) => s.dates.forEach((dt) => dateSet.add(dt)))
  if (d.benchmark_series) d.benchmark_series.dates.forEach((dt) => dateSet.add(dt))
  const dates = Array.from(dateSet).sort()
  const idxOf = (dt: string) => dates.indexOf(dt)

  const nameOf = (sym: string) => {
    const info = d.symbols_info.find((x) => x.symbol === sym)
    return info?.name || sym
  }

  const series: any[] = []
  const legendData: string[] = []
  let i = 0
  for (const [sym, s] of Object.entries(d.window_returns)) {
    const name = nameOf(sym)
    legendData.push(name)
    const arr = new Array(dates.length).fill(null)
    s.dates.forEach((dt, k) => {
      const idx = idxOf(dt)
      if (idx >= 0) arr[idx] = s.returns[k]
    })
    series.push({
      name, type: 'line', smooth: true, connectNulls: true, symbol: 'none',
      data: arr,
      lineStyle: { width: 2, color: PALETTE[i % PALETTE.length] },
      itemStyle: { color: PALETTE[i % PALETTE.length] },
    })
    i++
  }
  // 基准（沪深300）
  if (d.benchmark_series && d.benchmark_name) {
    legendData.push(d.benchmark_name)
    const arr = new Array(dates.length).fill(null)
    d.benchmark_series.dates.forEach((dt, k) => {
      const idx = idxOf(dt)
      if (idx >= 0) arr[idx] = d.benchmark_series!.returns[k]
    })
    series.push({
      name: d.benchmark_name, type: 'line', connectNulls: true, symbol: 'none',
      data: arr,
      lineStyle: { width: 1.5, type: 'dashed', color: COLOR_BENCH },
      itemStyle: { color: COLOR_BENCH },
    })
  }

  // 事件日垂直线（日期并集中 ≤ event_date 的最近一日）+ 0 基准水平线
  let evIdx = -1
  dates.forEach((dt, k) => {
    if (dt <= d.event_date) evIdx = k
  })
  const markData: any[] = [
    { yAxis: 0, lineStyle: { color: '#888', type: 'dashed' }, label: { formatter: '0 基准', color: '#888', fontSize: 10 } },
  ]
  if (evIdx >= 0) {
    markData.push({ xAxis: evIdx, lineStyle: { color: COLOR_EVENT, type: 'solid' }, label: { formatter: '事件日', color: COLOR_EVENT, fontSize: 10 } })
  }
  if (series.length) {
    series[0].markLine = { symbol: 'none', silent: true, data: markData }
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', lineStyle: { color: tc.axisLine } },
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tc.tooltipText },
      formatter: (params: any) => {
        if (!params || !params.length) return ''
        let html = `<b>${params[0].axisValue}</b>`
        for (const p of params) {
          if (p.value == null) continue
          const c = p.seriesName === d.benchmark_name ? COLOR_BENCH : p.value >= 0 ? COLOR_UP : COLOR_DOWN
          html += `<br/>${p.marker}<span style="color:${c}">${p.seriesName}：${p.value >= 0 ? '+' : ''}${p.value.toFixed(2)}%</span>`
        }
        return html
      },
    },
    legend: { data: legendData, top: 0, type: 'scroll', textStyle: { color: tc.axisLabel, fontSize: 11 } },
    grid: { left: 60, right: 24, top: 40, bottom: 56 },
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel, fontSize: 10 },
      axisTick: { lineStyle: { color: tc.axisLine } },
    },
    yAxis: {
      type: 'value', name: '累计收益(%)', scale: true,
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel, formatter: (v: number) => `${v > 0 ? '+' : ''}${v}%` },
      splitLine: { lineStyle: { color: tc.splitLine } },
      nameTextStyle: { color: tc.axisLabel },
    },
    dataZoom: [{ type: 'inside' }, { type: 'slider', height: 16, bottom: 18, textStyle: { color: tc.axisLabel } }],
    series,
  } as echarts.EChartsOption
}

function render() {
  if (!chart || !props.data) return
  chart.setOption(buildOption(props.data), true)
}
function onResize() {
  chart?.resize()
}
onMounted(() => {
  if (el.value) {
    chart = echarts.init(el.value)
    render()
    window.addEventListener('resize', onResize)
  }
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
watch(() => props.data, render)
watch(theme, render)
</script>

<template>
  <div class="chart-wrap">
    <div ref="el" class="chart"></div>
    <LegendHint />
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
  height: 420px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
