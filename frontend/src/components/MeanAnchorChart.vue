<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { ChartSeries } from '../api'
import { theme } from '../composables/useTheme'

const props = defineProps<{ data: ChartSeries | null }>()

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

function buildOption(d: ChartSeries): echarts.EChartsOption {
  const tc = themeColors()
  const s = d.series
  const dates = d.dates

  const series: echarts.SeriesOption[] = [
    // ±15% 通道填充（lower→upper 的 markArea 不好做连续，用 stacked area 近似）
    // 用 upper 线 + lower 线 + 上层透明填充实现通道
    {
      name: '通道上沿(+15%)',
      type: 'line',
      data: s.upper || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      lineStyle: { color: '#ee6666', width: 1, type: 'dashed' as const, opacity: 0.6 },
      itemStyle: { color: 'transparent' },
      stack: 'channel',
      areaStyle: { color: 'rgba(128,128,128,0.12)' },
    },
    {
      name: '通道下沿(-15%)',
      type: 'line',
      data: s.lower || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      lineStyle: { color: '#3ba272', width: 1, type: 'dashed' as const, opacity: 0.6 },
      itemStyle: { color: 'transparent' },
      stack: 'channel-hidden',
      areaStyle: { color: 'transparent' },
    },
    {
      name: '收盘价',
      type: 'line',
      data: s.close || [],
      symbol: 'none',
      smooth: false,
      connectNulls: false,
      itemStyle: { color: tc.axisLabel },
      lineStyle: { width: 1, opacity: 0.8 },
    },
    {
      name: '5年均线',
      type: 'line',
      data: s.ma || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: '#5470c6' },
      lineStyle: { width: 2 },
    },
    {
      name: '60日均线',
      type: 'line',
      data: s.ma60 || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: '#91cc75' },
      lineStyle: { width: 1.2, opacity: 0.7 },
    },
    {
      name: '卖出线(+28%)',
      type: 'line',
      data: s.sell_line || [],
      symbol: 'none',
      smooth: true,
      connectNulls: true,
      itemStyle: { color: '#fac858' },
      lineStyle: { width: 1.5, type: 'dotted' as const },
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
    legend: {
      data: ['收盘价', '5年均线', '60日均线', '卖出线(+28%)', '通道上沿(+15%)', '通道下沿(-15%)'],
      top: 0,
      textStyle: { color: tc.axisLabel, fontSize: 11 },
    },
    grid: { left: 60, right: 36, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
    },
    yAxis: {
      type: 'value',
      name: '点位',
      scale: true,
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
    <LegendHint text="灰带=±15%估值通道，蓝线=5年均线（估值锚），绿线=60日均线，橙点线=卖出线(+28%)" />
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
  height: 500px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
