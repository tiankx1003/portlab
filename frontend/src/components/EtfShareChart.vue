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
  const vals = d.series.change || []
  // 正值红（资金流入），负值绿（资金流出）——A 股惯例
  const colors = vals.map((v) => (v == null ? '#909399' : v >= 0 ? '#ee6666' : '#3ba272'))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tc.tooltipText },
      valueFormatter: (v: number | string) =>
        typeof v === 'number' ? `${(v / 1e4).toFixed(2)} 亿份` : String(v),
    },
    grid: { left: 64, right: 36, top: 24, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
    },
    yAxis: {
      type: 'value',
      name: '份额变动(万份)',
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { lineStyle: { color: tc.splitLine } },
      nameTextStyle: { color: tc.axisLabel },
    },
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', height: 18, bottom: 24, borderColor: tc.axisLine, textStyle: { color: tc.axisLabel } },
    ],
    series: [
      {
        name: '份额变动',
        type: 'bar',
        data: vals.map((v, i) => ({ value: v, itemStyle: { color: colors[i] } })),
      },
    ],
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
    <LegendHint text="红柱=份额净申购（资金流入），绿柱=净赎回（资金流出）。持续净申购=机构/国家队吸筹" />
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
  height: 320px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
