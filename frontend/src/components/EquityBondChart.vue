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
  const hasIdx = s.index_close?.some((v) => v != null) ?? false

  // ECharts 4 子图布局（grid 数组）
  const grids = [
    { left: 60, right: hasIdx ? 56 : 36, top: 50, height: '32%' },   // 子图1：比价+指数
    { left: 60, right: 36, top: '46%', height: '16%' },              // 子图2：收益率对比
    { left: 60, right: 36, top: '66%', height: '14%' },              // 子图3：分位数
    { left: 60, right: hasIdx ? 56 : 36, top: '84%', height: '12%' }, // 子图4：PE+指数
  ]
  const xAxes = grids.map((_, i) => ({
    type: 'category' as const,
    gridIndex: i,
    data: dates,
    show: i === 3,
    axisLine: { lineStyle: { color: tc.axisLine } },
    axisLabel: i === 3 ? { color: tc.axisLabel } : { show: false },
  }))

  const series: echarts.SeriesOption[] = []

  // ---- 子图1：股债比价 + ±1σ通道 + 指数(右轴) ----
  // ±1σ 通道填充（p1 上沿→n1 下沿，用 stacked area 模拟）
  series.push({
    name: '比价', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
    data: s.ratio || [], symbol: 'none', smooth: true, connectNulls: false,
    itemStyle: { color: '#5470c6' }, lineStyle: { width: 2 },
    z: 3,
  })
  series.push({
    name: '均值', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
    data: s.mean || [], symbol: 'none', smooth: true, connectNulls: true,
    itemStyle: { color: '#91cc75' }, lineStyle: { width: 1, type: 'dashed' as const },
    z: 2,
  })
  // ±1σ 通道：上沿 p1
  series.push({
    name: '+1σ', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
    data: s.p1 || [], symbol: 'none', smooth: true, connectNulls: true,
    lineStyle: { color: 'transparent' }, areaStyle: { color: 'rgba(84,112,198,0.10)' },
    stack: 'sigma1-top', z: 1, silent: true,
  })
  // -1σ 下沿（从 p1 底部填到 n1）
  series.push({
    name: '-1σ', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
    data: s.n1 || [], symbol: 'none', smooth: true, connectNulls: true,
    lineStyle: { color: 'transparent' }, areaStyle: { color: 'rgba(255,255,255,0)' },
    stack: 'sigma1-bot', z: 1, silent: true,
  })
  if (hasIdx) {
    series.push({
      name: '指数', type: 'line', xAxisIndex: 0, yAxisIndex: 1,
      data: s.index_close || [], symbol: 'none', smooth: true, connectNulls: true,
      itemStyle: { color: '#ee6666' }, lineStyle: { width: 1, opacity: 0.5 },
    })
  }

  // ---- 子图2：股票收益率 vs 国债收益率 ----
  series.push({
    name: '盈利收益率', type: 'line', xAxisIndex: 1, yAxisIndex: 2,
    data: s.stock_yield || [], symbol: 'none', smooth: true, connectNulls: false,
    itemStyle: { color: '#ee6666' }, lineStyle: { width: 1.2 },
  })
  series.push({
    name: '国债收益率', type: 'line', xAxisIndex: 1, yAxisIndex: 2,
    data: s.bond_yield || [], symbol: 'none', smooth: true, connectNulls: false,
    itemStyle: { color: '#fac858' }, lineStyle: { width: 1.2 },
  })

  // ---- 子图3：历史分位数 ----
  series.push({
    name: '比价分位', type: 'line', xAxisIndex: 2, yAxisIndex: 3,
    data: s.percentile || [], symbol: 'none', smooth: true, connectNulls: false,
    itemStyle: { color: '#73c0de' }, lineStyle: { width: 1.2 },
    areaStyle: { color: 'rgba(115,192,222,0.15)' },
    markLine: {
      symbol: 'none', silent: true,
      data: [
        { yAxis: 80, lineStyle: { color: '#3ba272', type: 'dotted' as const }, label: { formatter: '高性价比80%', color: '#3ba272', fontSize: 9 } },
        { yAxis: 20, lineStyle: { color: '#ee6666', type: 'dotted' as const }, label: { formatter: '低性价比20%', color: '#ee6666', fontSize: 9 } },
      ],
    },
  })

  // ---- 子图4：PE + 指数(右轴) ----
  series.push({
    name: 'PE-TTM', type: 'line', xAxisIndex: 3, yAxisIndex: 4,
    data: s.pe_ttm || [], symbol: 'none', smooth: true, connectNulls: false,
    itemStyle: { color: '#9a60b4' }, lineStyle: { width: 1.2 },
  })
  if (hasIdx) {
    series.push({
      name: '指数', type: 'line', xAxisIndex: 3, yAxisIndex: 5,
      data: s.index_close || [], symbol: 'none', smooth: true, connectNulls: true,
      itemStyle: { color: '#ee6666' }, lineStyle: { width: 1, opacity: 0.5 },
    })
  }

  const yAxes = [
    { gridIndex: 0, type: 'value' as const, name: '比价', scale: true,
      axisLine: { lineStyle: { color: tc.axisLine } }, axisLabel: { color: tc.axisLabel, fontSize: 10 },
      splitLine: { lineStyle: { color: tc.splitLine } }, nameTextStyle: { color: tc.axisLabel, fontSize: 10 } },
    ...(hasIdx ? [{ gridIndex: 0, type: 'value' as const, name: '指数', scale: true, position: 'right' as const,
      axisLine: { lineStyle: { color: tc.axisLine } }, axisLabel: { color: tc.axisLabel, fontSize: 10 },
      splitLine: { show: false }, nameTextStyle: { color: tc.axisLabel, fontSize: 10 } }] : []),
    { gridIndex: 1, type: 'value' as const, name: '收益率%', scale: true,
      axisLine: { lineStyle: { color: tc.axisLine } }, axisLabel: { color: tc.axisLabel, fontSize: 10 },
      splitLine: { lineStyle: { color: tc.splitLine } }, nameTextStyle: { color: tc.axisLabel, fontSize: 10 } },
    { gridIndex: 2, type: 'value' as const, name: '分位%', min: 0, max: 100,
      axisLine: { lineStyle: { color: tc.axisLine } }, axisLabel: { color: tc.axisLabel, fontSize: 10 },
      splitLine: { lineStyle: { color: tc.splitLine } }, nameTextStyle: { color: tc.axisLabel, fontSize: 10 } },
    { gridIndex: 3, type: 'value' as const, name: 'PE', scale: true,
      axisLine: { lineStyle: { color: tc.axisLine } }, axisLabel: { color: tc.axisLabel, fontSize: 10 },
      splitLine: { lineStyle: { color: tc.splitLine } }, nameTextStyle: { color: tc.axisLabel, fontSize: 10 } },
    ...(hasIdx ? [{ gridIndex: 3, type: 'value' as const, name: '指数', scale: true, position: 'right' as const,
      axisLine: { lineStyle: { color: tc.axisLine } }, axisLabel: { color: tc.axisLabel, fontSize: 10 },
      splitLine: { show: false }, nameTextStyle: { color: tc.axisLabel, fontSize: 10 } }] : []),
  ]

  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', link: [{ xAxisIndex: 'all' }] },
      backgroundColor: tc.tooltipBg, borderColor: tc.tooltipBorder, borderWidth: 1,
      textStyle: { color: tc.tooltipText, fontSize: 11 },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    legend: {
      data: ['比价', '均值', '指数', '盈利收益率', '国债收益率', '比价分位', 'PE-TTM'],
      top: 0, textStyle: { color: tc.axisLabel, fontSize: 11 },
    },
    grid: grids,
    xAxis: xAxes as any,
    yAxis: yAxes as any,
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1, 2, 3] },
      { type: 'slider', xAxisIndex: [0, 1, 2, 3], height: 16, bottom: 10, borderColor: tc.axisLine, textStyle: { color: tc.axisLabel } },
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
    <LegendHint text="子图1：比价(蓝)+均值(绿虚)+±1σ通道(蓝带)+指数(红,右轴) 子图2：盈利收益率 vs 国债 子图3：分位数(80%高性价比) 子图4：PE-TTM+指数" />
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
  height: 720px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
