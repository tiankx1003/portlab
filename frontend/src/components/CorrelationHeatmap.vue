<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { theme } from '../composables/useTheme'

/** 通用相关性输入：symbols_name（组合回测）或 symbols_info（事件看板）二选一提供名称。 */
export interface CorrelationInput {
  correlation_symbols: string[]
  correlation_matrix: number[][]
  symbols_name?: string[]
  symbols_info?: { symbol: string; name: string }[]
}

const props = defineProps<{ data: CorrelationInput | null }>()

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

function buildOption(d: CorrelationInput): echarts.EChartsOption {
  const tc = themeColors()
  const syms = d.correlation_symbols
  const labels = syms.map((s, i) => {
    if (d.symbols_name && d.symbols_name[i]) return d.symbols_name[i]
    const info = d.symbols_info?.find((x) => x.symbol === s)
    return info?.name || s
  })
  const data: [number, number, number][] = []
  for (let r = 0; r < syms.length; r++) {
    for (let c = 0; c < syms.length; c++) {
      const v = d.correlation_matrix?.[r]?.[c]
      data.push([c, r, v == null ? 0 : v])
    }
  }
  return {
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tc.tooltipText },
      formatter: (p: any) => {
        const [c, r, v] = p.value
        const a = labels[r] || syms[r]
        const b = labels[c] || syms[c]
        const color = v >= 0.7 || v <= -0.7 ? '#ee6666' : tc.tooltipText
        return `${a} × ${b}<br/>相关系数：<b style="color:${color}">${(v as number).toFixed(2)}</b>`
      },
    },
    grid: { left: 110, right: 24, top: 24, bottom: 90 },
    xAxis: {
      type: 'category', data: labels, splitArea: { show: true },
      axisLabel: { color: tc.axisLabel, fontSize: 10, rotate: 38 },
      axisLine: { lineStyle: { color: tc.axisLine } },
    },
    yAxis: {
      type: 'category', data: labels, splitArea: { show: true },
      axisLabel: { color: tc.axisLabel, fontSize: 10 },
      axisLine: { lineStyle: { color: tc.axisLine } },
    },
    visualMap: {
      min: -1, max: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 12,
      textStyle: { color: tc.axisLabel, fontSize: 10 },
      inRange: { color: ['#5470c6', '#cdd3df', '#ee6666'] }, // 负相关蓝 / 0 中性 / 正相关红
    },
    series: [
      {
        type: 'heatmap', data, label: { show: syms.length <= 10, color: '#333', fontSize: 9, formatter: (p: any) => (p.value[2] as number).toFixed(2) },
        emphasis: { itemStyle: { shadowBlur: 8, shadowColor: 'rgba(0,0,0,0.4)' } },
      },
    ],
  } as echarts.EChartsOption
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
  <div ref="el" class="heatmap"></div>
</template>

<style scoped>
.heatmap {
  width: 100%;
  height: 460px;
}
</style>
