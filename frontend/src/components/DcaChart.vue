<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { ChartData } from '../api'
import { theme } from '../composables/useTheme'

// A 股配色惯例：红涨绿跌
const COLOR_UP = '#ee6666' // 盈利 / 上涨
const COLOR_DOWN = '#3ba272' // 亏损 / 下跌
const COLOR_BENCH = '#9b6bff' // 基准（沪深300）

const props = defineProps<{ data: ChartData | null }>()

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

function buildOption(d: ChartData): echarts.EChartsOption {
  const tc = themeColors()
  const hasBench = !!d.benchmark_name && d.benchmark_returns.some((v) => v != null)

  const series: echarts.SeriesOption[] = [
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
      name: '亏损', type: 'bar', yAxisIndex: 0, stack: 'pnl', barWidth: '60%',
      data: d.pnl.map((v) => (v < 0 ? v : 0)),
      itemStyle: { color: COLOR_DOWN },
    },
    {
      name: '盈利', type: 'bar', yAxisIndex: 0, stack: 'pnl', barWidth: '60%',
      data: d.pnl.map((v) => (v >= 0 ? v : 0)),
      itemStyle: { color: COLOR_UP },
    },
    {
      name: '收益率', type: 'line', smooth: true, yAxisIndex: 1,
      data: d.return_rate, symbol: 'none',
      itemStyle: { color: '#ee9c2a' }, lineStyle: { width: 2 },
    },
  ]
  const legendData = ['市值', '成本', '亏损', '盈利', '收益率']
  if (hasBench) {
    legendData.push(d.benchmark_name)
    series.push({
      name: d.benchmark_name, type: 'line', yAxisIndex: 1,
      data: d.benchmark_returns as number[], symbol: 'none',
      itemStyle: { color: COLOR_BENCH }, lineStyle: { width: 1.5, type: 'dotted' },
      connectNulls: false,
    })
  }

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
        const mv = d.market_value[i]
        const cost = d.total_cost[i]
        const pnl = d.pnl[i]
        const rate = d.return_rate[i]
        const inv = d.invest_days[i]
        const dr = d.deduction_rates[i]
        const aa = d.actual_amounts[i]
        const pnlColor = pnl >= 0 ? COLOR_UP : COLOR_DOWN
        const rateColor = rate >= 0 ? COLOR_UP : COLOR_DOWN
        const bench = d.benchmark_returns[i]
        return (
          `${d.dates[i]}` +
          `<br/>市值：${mv.toFixed(2)}` +
          `<br/>成本：${cost.toFixed(2)}` +
          `<br/>盈亏：<span style="color:${pnlColor};font-weight:600">${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}</span>` +
          `<br/>收益率：<span style="color:${rateColor};font-weight:600">${rate.toFixed(2)}%</span>` +
          (hasBench && bench != null ? `<br/>${d.benchmark_name}：<span style="color:${COLOR_BENCH}">${bench.toFixed(2)}%</span>` : '') +
          (inv ? `<br/>📌 定投日` : '') +
          (inv && dr != null
            ? `<br/>扣款率：${(dr * 100).toFixed(0)}%　实投：${aa != null ? aa.toFixed(2) : '-'}`
            : '')
        )
      },
    },
    legend: { data: legendData, top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 64, right: 72, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      axisTick: { lineStyle: { color: tc.axisLine } },
    },
    yAxis: [
      {
        type: 'value', name: '金额(元)', scale: true,
        axisLine: { show: true, lineStyle: { color: tc.axisLine } },
        axisLabel: { color: tc.axisLabel },
        splitLine: { lineStyle: { color: tc.splitLine } },
        nameTextStyle: { color: tc.axisLabel },
      },
      {
        type: 'value', name: '收益率(%)', scale: true,
        axisLine: { show: true, lineStyle: { color: tc.axisLine } },
        axisLabel: { color: tc.axisLabel },
        splitLine: { show: false },
        nameTextStyle: { color: tc.axisLabel },
      },
    ],
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
  <div ref="el" class="chart"></div>
</template>

<style scoped>
.chart {
  width: 100%;
  height: 480px;
}
</style>
