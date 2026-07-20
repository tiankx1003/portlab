<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import { theme } from '../composables/useTheme'

// 多曲线分类色板（与 EventImpactChart 一致）
const PALETTE = ['#5470c6', '#ee6666', '#3ba272', '#fac858', '#ee9c2a', '#73c0de', '#fc8452', '#9a60b4']

interface NavSeries {
  name: string
  dates: string[]
  nav: number[]
}
const props = defineProps<{ series: NavSeries[] }>()

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

function buildOption(series: NavSeries[]): echarts.EChartsOption {
  const tc = themeColors()
  // 日期并集
  const dateSet = new Set<string>()
  series.forEach((s) => s.dates.forEach((d) => dateSet.add(d)))
  const dates = Array.from(dateSet).sort()
  const idxOf = (d: string) => dates.indexOf(d)

  const echartsSeries: any[] = []
  const legendData: string[] = []
  series.forEach((s, i) => {
    legendData.push(s.name)
    const arr = new Array(dates.length).fill(null)
    s.dates.forEach((d, k) => {
      const idx = idxOf(d)
      if (idx >= 0) arr[idx] = s.nav[k]
    })
    echartsSeries.push({
      name: s.name, type: 'line', smooth: true, connectNulls: true, symbol: 'none',
      data: arr,
      lineStyle: { width: 2, color: PALETTE[i % PALETTE.length] },
      itemStyle: { color: PALETTE[i % PALETTE.length] },
    })
  })

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
          html += `<br/>${p.marker}${p.seriesName}：<b>${p.value.toFixed(2)}</b>`
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
      type: 'value', name: '归一化净值(起点=100)', scale: true,
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { lineStyle: { color: tc.splitLine } },
      nameTextStyle: { color: tc.axisLabel },
    },
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', height: 16, bottom: 18, borderColor: tc.axisLine, textStyle: { color: tc.axisLabel } },
    ],
    series: echartsSeries,
  } as echarts.EChartsOption
}

function render() {
  if (!chart || !props.series.length) return
  chart.setOption(buildOption(props.series), true)
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
watch(() => props.series, render, { deep: true })
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
