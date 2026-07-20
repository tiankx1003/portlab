<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import { theme } from '../composables/useTheme'

// 多标的分类色板（与 EventImpactChart 一致）
const PALETTE = ['#5470c6', '#ee6666', '#3ba272', '#fac858', '#ee9c2a', '#73c0de', '#fc8452', '#9a60b4']

const props = defineProps<{ weights: number[]; names: string[] }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function themeColors() {
  const dark = theme.value === 'dark'
  return {
    axisLabel: dark ? '#a0a0a8' : '#6e7079',
    tooltipBg: dark ? '#2a2a30' : '#ffffff',
    tooltipBorder: dark ? '#3a3a42' : '#dddddd',
    tooltipText: dark ? '#e8e8ec' : '#333333',
  }
}

function buildOption(weights: number[], names: string[]): echarts.EChartsOption {
  const tc = themeColors()
  const data = weights.map((w, i) => ({
    name: names[i] || `标的${i + 1}`,
    value: w,
    itemStyle: { color: PALETTE[i % PALETTE.length] },
  }))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      backgroundColor: tc.tooltipBg,
      borderColor: tc.tooltipBorder,
      borderWidth: 1,
      textStyle: { color: tc.tooltipText },
      formatter: (p: any) => `${p.name}<br/>权重：<b>${(p.value * 100).toFixed(1)}%</b>`,
    },
    legend: { type: 'scroll', orient: 'vertical', right: 8, top: 'middle', textStyle: { color: tc.axisLabel, fontSize: 11 } },
    series: [
      {
        type: 'pie', radius: ['38%', '66%'], center: ['40%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}\n{d}%', fontSize: 11, color: tc.axisLabel },
        data,
      },
    ],
  } as echarts.EChartsOption
}

function render() {
  if (!chart) return
  chart.setOption(buildOption(props.weights, props.names), true)
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
watch(() => [props.weights, props.names], render, { deep: true })
watch(theme, render)
</script>

<template>
  <div ref="el" class="pie"></div>
</template>

<style scoped>
.pie {
  width: 100%;
  height: 320px;
}
</style>
