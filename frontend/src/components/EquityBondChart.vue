<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { ChartSeries } from '../api'
import { theme } from '../composables/useTheme'

const props = defineProps<{ data: ChartSeries | null }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const COLOR_RATIO = '#ee6666' // 比价主曲线（红）
const COLOR_MEAN = '#909399' // 滚动均值（灰）
const COLOR_IDX = '#d4a574' // 指数点位（浅棕，右轴）

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

// ±σ 通道线颜色（由近到远渐淡）
const sigmaColors = ['#fac858', '#91cc75', '#73c0de', '#fc8452', '#9a60b4', '#ea7ccc']

function buildOption(d: ChartSeries): echarts.EChartsOption {
  const tc = themeColors()
  const s = d.series
  const hasIdx = s.index_close?.some((v) => v != null) ?? false

  const sigmaLines = [
    { key: 'p3', label: '+3σ' },
    { key: 'p2', label: '+2σ' },
    { key: 'p1', label: '+1σ' },
    { key: 'n1', label: '-1σ' },
    { key: 'n2', label: '-2σ' },
    { key: 'n3', label: '-3σ' },
  ]
    .filter((l) => s[l.key])
    .map((l, i) => {
      const vals = s[l.key] as (number | null)[]
      const last = [...vals].reverse().find((v) => v != null)
      return {
        yAxis: last,
        lineStyle: { color: sigmaColors[i], type: 'dashed' as const, opacity: 0.6 },
        label: { formatter: `${l.label}`, color: sigmaColors[i], fontSize: 10, position: 'insideEndTop' as const },
      }
    })

  const series: echarts.SeriesOption[] = [
    {
      name: '股债比价',
      type: 'line',
      yAxisIndex: 0,
      data: s.ratio || [],
      symbol: 'none',
      smooth: true,
      connectNulls: false,
      itemStyle: { color: COLOR_RATIO },
      lineStyle: { width: 2 },
      markLine: { symbol: 'none', silent: true, data: sigmaLines },
    },
    {
      name: '滚动均值',
      type: 'line',
      yAxisIndex: 0,
      data: s.mean || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: COLOR_MEAN },
      lineStyle: { width: 1.5, type: 'dashed' },
    },
  ]

  if (hasIdx) {
    series.push({
      name: '指数点位',
      type: 'line',
      yAxisIndex: 1,
      data: s.index_close || [],
      symbol: 'none',
      connectNulls: true,
      itemStyle: { color: COLOR_IDX },
      lineStyle: { width: 1.5 },
    })
  }

  const yAxis: Record<string, unknown>[] = [
    {
      type: 'value',
      name: '股债比价',
      scale: true,
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { lineStyle: { color: tc.splitLine } },
      nameTextStyle: { color: tc.axisLabel },
    },
  ]
  if (hasIdx) {
    yAxis.push({
      type: 'value',
      name: '指数点位',
      scale: true,
      position: 'right',
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { show: false },
      nameTextStyle: { color: tc.axisLabel },
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
    },
    legend: {
      data: ['股债比价', '滚动均值', ...(hasIdx ? ['指数点位'] : [])],
      top: 0,
      textStyle: { color: tc.axisLabel },
    },
    grid: { left: 60, right: hasIdx ? 64 : 36, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
    },
    yAxis: yAxis as NonNullable<echarts.EChartsOption['yAxis']>,
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
    <LegendHint text="红线=股债比价，灰虚线=5年滚动均值，彩虚线=±1/±2/±3σ通道。点击图例隐藏曲线" />
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
