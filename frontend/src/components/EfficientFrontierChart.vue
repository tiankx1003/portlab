<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { FrontierData } from '../api'
import { theme } from '../composables/useTheme'

// 有效前沿配色
const COLOR_FRONTIER = '#5470c6' // 前沿曲线（蓝）
const COLOR_SINGLE = '#9aa4b2' // 单标的点（灰）
const COLOR_MS = '#ee6666' // 最大夏普（红）
const COLOR_MV = '#3ba272' // 最小方差（绿）

const props = defineProps<{ data: FrontierData | null }>()
const emit = defineEmits<{ (e: 'select', idx: number): void }>()

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

function buildOption(d: FrontierData): echarts.EChartsOption {
  const tc = themeColors()
  const frontierPts = d.volatilities.map((v, i) => [v, d.returns[i]])
  const singlePts = d.single_assets.map((a) => ({
    value: [a.volatility, a.ret],
    name: a.name,
  }))

  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tc.tooltipText },
      formatter: (p: any) => {
        const [x, y] = p.value
        return `${p.seriesName}<br/>波动：${Number(x).toFixed(2)}%<br/>收益：${Number(y).toFixed(2)}%`
      },
    },
    legend: { top: 0, textStyle: { color: tc.axisLabel, fontSize: 11 } },
    grid: { left: 64, right: 24, top: 40, bottom: 48 },
    xAxis: {
      type: 'value', name: '年化波动(%)', scale: true,
      nameTextStyle: { color: tc.axisLabel },
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { lineStyle: { color: tc.splitLine } },
    },
    yAxis: {
      type: 'value', name: '年化收益(%)', scale: true,
      nameTextStyle: { color: tc.axisLabel },
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { show: false },
    },
    series: [
      {
        name: '有效前沿', type: 'line', smooth: true,
        data: frontierPts, symbol: 'circle', symbolSize: 6,
        lineStyle: { color: COLOR_FRONTIER, width: 2 },
        itemStyle: { color: COLOR_FRONTIER },
      },
      {
        name: '单标的', type: 'scatter',
        data: singlePts, symbolSize: 10,
        itemStyle: { color: COLOR_SINGLE },
        label: {
          show: true, position: 'top', fontSize: 10, color: tc.axisLabel,
          formatter: (p: any) => p.data.name,
        },
      },
      {
        name: '最大夏普', type: 'scatter',
        data: [[d.max_sharpe.volatility, d.max_sharpe.ret]], symbolSize: 16,
        itemStyle: { color: COLOR_MS },
        label: { show: true, formatter: '最大夏普', position: 'right', color: COLOR_MS, fontSize: 11 },
      },
      {
        name: '最小方差', type: 'scatter',
        data: [[d.min_variance.volatility, d.min_variance.ret]], symbolSize: 16,
        itemStyle: { color: COLOR_MV },
        label: { show: true, formatter: '最小方差', position: 'right', color: COLOR_MV, fontSize: 11 },
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
    // 点击前沿点 → 联动权重饼图
    chart.on('click', (params: any) => {
      if (params.seriesName === '有效前沿') emit('select', params.dataIndex)
    })
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
  height: 440px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
