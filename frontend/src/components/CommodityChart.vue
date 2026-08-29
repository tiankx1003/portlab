<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { ChartSeries } from '../api'
import { theme } from '../composables/useTheme'

const props = defineProps<{ data: ChartSeries | null }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const COLORS: Record<string, string> = {
  JM0: '#5470c6', // 焦煤（蓝）
  CU0: '#ee6666', // 沪铜（红）
  RB0: '#3ba272', // 螺纹钢（绿）
  BDI: '#fac858', // BDI（金）
}
const LABELS: Record<string, string> = {
  JM0: '焦煤',
  CU0: '沪铜',
  RB0: '螺纹钢',
  BDI: 'BDI运价指数',
}

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

function buildOption(d: ChartSeries): echarts.EChartsOption {
  const tc = themeColors()
  const s = d.series
  const series: echarts.SeriesOption[] = []
  const legendData: string[] = []

  for (const key of ['JM0', 'CU0', 'RB0', 'BDI']) {
    if (!s[key] || !s[key].some((v) => v != null)) continue
    legendData.push(LABELS[key])
    series.push({
      name: LABELS[key],
      type: 'line',
      yAxisIndex: 0,
      data: s[key],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: COLORS[key] },
      lineStyle: { width: 1.8 },
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
      valueFormatter: (v: number | string) => (typeof v === 'number' ? v.toFixed(1) : String(v)),
    },
    legend: { data: legendData, top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 56, right: 36, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
    },
    yAxis: {
      type: 'value',
      name: '归一化(首日=100)',
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { lineStyle: { color: tc.splitLine } },
      nameTextStyle: { color: tc.axisLabel },
    },
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
    <LegendHint text="归一化至首日=100，便于跨品种对比走势。上行=利好周期/红利成分股" />
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
  height: 380px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
