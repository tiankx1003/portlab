<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { PortfolioChartData } from '../api'
import { theme } from '../composables/useTheme'

const COLOR_NAV = '#5470c6' // 组合净值（蓝）
const COLOR_BENCH = '#9b6bff' // 基准（紫）
const COLOR_DOWN = '#3ba272' // 回撤（绿）

const props = defineProps<{ data: PortfolioChartData | null }>()

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

function buildOption(d: PortfolioChartData): echarts.EChartsOption {
  const tc = themeColors()
  const series: echarts.SeriesOption[] = [
    {
      name: '组合净值', type: 'line', smooth: true, yAxisIndex: 0,
      data: d.nav, symbol: 'none',
      itemStyle: { color: COLOR_NAV }, lineStyle: { width: 2 },
    },
    {
      name: '回撤', type: 'line', yAxisIndex: 1,
      data: d.drawdown, symbol: 'none', connectNulls: true,
      itemStyle: { color: COLOR_DOWN }, lineStyle: { width: 1 },
      areaStyle: { opacity: 0.1 },
    },
  ]
  const legendData = ['组合净值', '回撤']
  if (d.benchmark_name && d.benchmark_nav.some((v) => v != null)) {
    legendData.unshift(d.benchmark_name)
    series.unshift({
      name: d.benchmark_name, type: 'line', yAxisIndex: 0,
      data: d.benchmark_nav as number[], symbol: 'none', connectNulls: true,
      itemStyle: { color: COLOR_BENCH }, lineStyle: { width: 1.5, type: 'dashed' },
    })
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
        const i = params[0].dataIndex
        const f4 = (v: number | null | undefined) => (v == null ? '-' : v.toFixed(4))
        let html = `${d.dates[i]}`
        for (const p of params) {
          if (p.value == null) continue
          const unit = p.seriesName === '回撤' ? '%' : ''
          html += `<br/>${p.marker}${p.seriesName}：${f4(p.value)}${unit}`
        }
        return html
      },
    },
    legend: { data: legendData, top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 64, right: 64, top: 40, bottom: 64 },
    xAxis: {
      type: 'category', data: d.dates, boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      axisTick: { lineStyle: { color: tc.axisLine } },
    },
    yAxis: [
      {
        type: 'value', name: '净值(起点=1)', scale: true,
        axisLine: { show: true, lineStyle: { color: tc.axisLine } },
        axisLabel: { color: tc.axisLabel },
        splitLine: { lineStyle: { color: tc.splitLine } },
        nameTextStyle: { color: tc.axisLabel },
      },
      {
        type: 'value', name: '回撤(%)', scale: true,
        axisLine: { show: true, lineStyle: { color: tc.axisLine } },
        axisLabel: { color: tc.axisLabel, formatter: (v: number) => `${v}%` },
        splitLine: { show: false },
        nameTextStyle: { color: tc.axisLabel },
      },
    ],
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', height: 18, bottom: 24, borderColor: tc.axisLine, textStyle: { color: tc.axisLabel } },
    ],
    series,
  }
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
  height: 460px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
