<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { OverlayData } from '../api'
import { theme } from '../composables/useTheme'

// A 股配色：涨跌幅红涨绿跌
const COLOR_UP = '#ee6666'
const COLOR_DOWN = '#3ba272'
const PALETTE = ['#5470c6', '#ee6666', '#3ba272', '#fac858', '#73c0de', '#9b6bff', '#fc8452']

const props = defineProps<{ data: OverlayData | null }>()

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

function buildOption(d: OverlayData): echarts.EChartsOption {
  const tc = themeColors()
  const base = d.base || 1

  const series = d.series.map((s, idx) => ({
    name: `${s.name_cn}（${s.index_code}）`,
    type: 'line',
    data: s.normalized,
    symbol: 'none',
    smooth: true,
    connectNulls: false,
    itemStyle: { color: PALETTE[idx % PALETTE.length] },
    lineStyle: { width: 2 },
  })) as echarts.SeriesOption[]

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
        const f4 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(4))
        let out = `${d.dates[i]}（归一化基准 = ${base}）`
        for (const p of params) {
          const v = p.value
          const pct = v == null ? null : (v / base - 1) * 100
          const pctColor = pct == null ? tc.axisLabel : pct >= 0 ? COLOR_UP : COLOR_DOWN
          out += `<br/><span style="color:${p.color}">●</span> ${p.seriesName}：${f4(v)}` +
            (pct == null ? '' : `　<span style="color:${pctColor};font-weight:600">${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%</span>`)
        }
        return out
      },
    },
    legend: { type: 'scroll', top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 64, right: 36, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      axisTick: { lineStyle: { color: tc.axisLine } },
    },
    yAxis: {
      type: 'value',
      name: `归一化(起点=${base})`,
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
    <LegendHint text="归一化对象为 PE-TTM；起点=基准值，红涨绿跌为相对起点的估值变动" />
  </div>
</template>

<style scoped>
.chart-wrap {
  position: relative;
  width: 100%;
  height: 520px;
}
.chart {
  width: 100%;
  height: 100%;
}
</style>
