<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { ChartData } from '../api'

const props = defineProps<{ data: ChartData | null }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function buildOption(d: ChartData): echarts.EChartsOption {
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      formatter: (params: any) => {
        const i = params[0].dataIndex
        const mv = d.market_value[i]
        const cost = d.total_cost[i]
        const pnl = d.pnl[i]
        const rate = d.return_rate[i]
        const inv = d.invest_days[i]
        return (
          `${d.dates[i]}` +
          `<br/>市值：${mv.toFixed(2)}` +
          `<br/>成本：${cost.toFixed(2)}` +
          `<br/>盈亏：${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}` +
          `<br/>收益率：${rate.toFixed(2)}%` +
          (inv ? `<br/>📌 定投日` : '')
        )
      },
    },
    legend: { data: ['市值', '成本', '盈亏', '收益率'], top: 0 },
    grid: { left: 64, right: 72, top: 40, bottom: 64 },
    xAxis: { type: 'category', data: d.dates, boundaryGap: true },
    yAxis: [
      { type: 'value', name: '金额(元)', scale: true },
      { type: 'value', name: '收益率(%)', scale: true },
    ],
    dataZoom: [
      { type: 'inside' },
      { type: 'slider', height: 18, bottom: 24 },
    ],
    series: [
      {
        name: '市值', type: 'line', smooth: true, yAxisIndex: 0,
        data: d.market_value, symbol: 'none',
        itemStyle: { color: '#5470c6' }, lineStyle: { width: 2 },
      },
      {
        name: '成本', type: 'line', yAxisIndex: 0,
        data: d.total_cost, symbol: 'none',
        itemStyle: { color: '#9aa4b2' }, lineStyle: { type: 'dashed', width: 1 },
      },
      {
        name: '盈亏', type: 'bar', yAxisIndex: 0, data: d.pnl, barWidth: '60%',
        itemStyle: { color: (p: any) => (p.value >= 0 ? '#3ba272' : '#ee6666') },
      },
      {
        name: '收益率', type: 'line', smooth: true, yAxisIndex: 1,
        data: d.return_rate, symbol: 'none',
        itemStyle: { color: '#ee9c2a' }, lineStyle: { width: 2 },
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
</script>

<template>
  <div ref="el" class="chart"></div>
</template>

<style scoped>
.chart {
  width: 100%;
  height: 480px;
}
</style>
