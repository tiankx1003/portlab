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
  pmi: '#5470c6',
  m1_yoy: '#ee6666',
  m2_yoy: '#fac858',
  sf_yoy: '#73c0de',
  ppi_yoy: '#3ba272',
}

const LABELS: Record<string, string> = {
  pmi: 'PMI',
  m1_yoy: 'M1同比%',
  m2_yoy: 'M2同比%',
  sf_yoy: '社融增速%',
  ppi_yoy: 'PPI同比%',
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

  for (const key of ['pmi', 'm1_yoy', 'm2_yoy', 'sf_yoy', 'ppi_yoy']) {
    if (!s[key] || !s[key].some((v) => v != null)) continue
    legendData.push(LABELS[key])
    const isPmi = key === 'pmi'
    series.push({
      name: LABELS[key],
      type: 'line',
      yAxisIndex: 0,
      data: s[key],
      symbol: 'circle',
      symbolSize: 4,
      smooth: true,
      connectNulls: false,
      itemStyle: { color: COLORS[key] },
      lineStyle: { width: isPmi ? 2.5 : 1.5 },
      markLine: isPmi
        ? {
            symbol: 'none',
            silent: true,
            label: { fontSize: 10, position: 'insideEndTop' as const },
            data: [
              {
                yAxis: 50,
                lineStyle: { color: '#ee6666', type: 'dashed' as const, opacity: 0.5 },
                label: { formatter: '荣枯线50', color: '#ee6666' },
              },
            ],
          }
        : undefined,
    })
  }

  // 0 轴参考线（对同比类指标）
  series[0] && (series[0] = {
    ...series[0],
    markLine: {
      symbol: 'none',
      silent: true,
      data: [{ yAxis: 0, lineStyle: { color: tc.axisLabel, type: 'dotted' as const } }],
    },
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
    },
    legend: { data: legendData, top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 60, right: 36, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
    },
    yAxis: {
      type: 'value',
      name: '指标值',
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
    <LegendHint text="PMI 荣枯线 50 为分水岭；M1/M2/社融/PPI 同比看 0 轴上下。点击图例隐藏曲线" />
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
