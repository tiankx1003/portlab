<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { ChartSeries } from '../api'
import { theme } from '../composables/useTheme'

const props = defineProps<{ data: ChartSeries | null }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

const COLOR_CLOSE = '#5470c6' // 全收益点位（蓝）
const COLOR_MA = '#fac858' // 5年均线（金）
const COLOR_DEV = '#ee6666' // 偏离度（红，右轴）

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

  const series: echarts.SeriesOption[] = [
    {
      name: '全收益点位',
      type: 'line',
      yAxisIndex: 0,
      data: s.close || [],
      symbol: 'none',
      smooth: true,
      connectNulls: false,
      itemStyle: { color: COLOR_CLOSE },
      lineStyle: { width: 2 },
    },
    {
      name: '5年均线',
      type: 'line',
      yAxisIndex: 0,
      data: s.ma || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: COLOR_MA },
      lineStyle: { width: 1.5, type: 'dashed' },
    },
    {
      name: '偏离度%',
      type: 'line',
      yAxisIndex: 1,
      data: s.deviation || [],
      symbol: 'none',
      connectNulls: true,
      itemStyle: { color: COLOR_DEV },
      lineStyle: { width: 1.5 },
      markLine: {
        symbol: 'none',
        silent: true,
        label: { fontSize: 10, position: 'insideEndTop' },
        data: [
          { yAxis: 0, lineStyle: { color: tc.axisLabel, type: 'dotted' as const }, label: { formatter: '均值', color: tc.axisLabel } },
          { yAxis: 20, lineStyle: { color: '#ee6666', type: 'dashed' as const, opacity: 0.5 }, label: { formatter: '+20% 过热', color: '#ee6666' } },
          { yAxis: -10, lineStyle: { color: '#3ba272', type: 'dashed' as const, opacity: 0.5 }, label: { formatter: '-10% 低估', color: '#3ba272' } },
        ],
      },
    },
  ]

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
    legend: { data: ['全收益点位', '5年均线', '偏离度%'], top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 60, right: 64, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
    },
    yAxis: [
      {
        type: 'value',
        name: '点位',
        scale: true,
        axisLine: { show: true, lineStyle: { color: tc.axisLine } },
        axisLabel: { color: tc.axisLabel },
        splitLine: { lineStyle: { color: tc.splitLine } },
        nameTextStyle: { color: tc.axisLabel },
      },
      {
        type: 'value',
        name: '偏离度%',
        scale: true,
        position: 'right',
        axisLine: { show: true, lineStyle: { color: tc.axisLine } },
        axisLabel: { color: tc.axisLabel, formatter: '{value}%' },
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
    <LegendHint text="蓝线=全收益点位，金虚线=5年均线，红线(右轴)=偏离度%。低于-10%=低估区" />
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
