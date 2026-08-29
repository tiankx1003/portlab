<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { ChartSeries } from '../api'
import { theme } from '../composables/useTheme'

const props = defineProps<{ data: ChartSeries | null }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const COLOR_MARGIN = '#ee6666' // 融资余额（红，左轴，面积）
const COLOR_SHORT = '#fac858' // 融券余额（金，左轴，线）
const COLOR_INDEX = '#5470c6' // 沪深300（蓝，右轴，虚线）

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
  const hasIdx = s.hs300?.some((v) => v != null) ?? false

  const series: echarts.SeriesOption[] = [
    {
      name: '融资余额',
      type: 'line',
      yAxisIndex: 0,
      data: s.rzye || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: COLOR_MARGIN },
      lineStyle: { width: 2 },
      areaStyle: { color: 'rgba(238,102,102,0.08)' },
    },
  ]
  if (s.rqye && s.rqye.some((v) => v != null)) {
    series.push({
      name: '融券余额',
      type: 'line',
      yAxisIndex: 0,
      data: s.rqye || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: COLOR_SHORT },
      lineStyle: { width: 1.5 },
    })
  }
  if (hasIdx) {
    series.push({
      name: '沪深300',
      type: 'line',
      yAxisIndex: 1,
      data: s.hs300 || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: COLOR_INDEX },
      lineStyle: { width: 1.5, type: 'dashed' as const },
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
      data: ['融资余额', ...(s.rqye?.some((v) => v != null) ? ['融券余额'] : []), ...(hasIdx ? ['沪深300'] : [])],
      top: 0,
      textStyle: { color: tc.axisLabel },
    },
    grid: { left: 64, right: hasIdx ? 64 : 36, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
    },
    yAxis: [
      {
        type: 'value' as const,
        name: '融资余额(亿)',
        scale: true,
        axisLine: { show: true, lineStyle: { color: tc.axisLine } },
        axisLabel: { color: tc.axisLabel },
        splitLine: { lineStyle: { color: tc.splitLine } },
        nameTextStyle: { color: tc.axisLabel },
      },
      ...(hasIdx
        ? [
            {
              type: 'value' as const,
              name: '沪深300',
              scale: true,
              position: 'right' as const,
              axisLine: { show: true, lineStyle: { color: tc.axisLine } },
              axisLabel: { color: tc.axisLabel },
              splitLine: { show: false },
              nameTextStyle: { color: tc.axisLabel },
            },
          ]
        : []),
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
    <LegendHint text="红线=融资余额(左轴)，蓝虚线=沪深300(右轴)。看杠杆资金与指数的相关性" />
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
