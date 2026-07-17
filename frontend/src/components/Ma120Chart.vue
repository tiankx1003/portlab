<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { Ma120ChartData } from '../api'
import { theme } from '../composables/useTheme'

// A 股配色惯例：红涨绿跌
const COLOR_UP = '#ee6666' // 盈利 / 买入标记
const COLOR_DOWN = '#3ba272' // 亏损
const COLOR_BENCH = '#9b6bff' // 基准（沪深300）
const COLOR_BUY = '#ee6666' // 买入标记（红）
const COLOR_SELL = '#3a7afe' // 卖出标记（蓝）
const COLOR_MA = '#fac858' // MA120 参考线（金）
const COLOR_CLOSE = '#73c0de' // 收盘价（浅蓝）

const props = defineProps<{ data: Ma120ChartData | null }>()

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

const SIGNAL_LABEL: Record<string, string> = { buy: '买入', sell: '卖出', hold: '观望' }

function buildOption(d: Ma120ChartData): echarts.EChartsOption {
  const tc = themeColors()
  const hasBench = !!d.benchmark_name && d.benchmark_returns.some((v) => v != null)

  const buyMarks = d.buy_points.map((p) => ({
    name: '买入',
    coord: [p.date, p.price],
    value: '买',
    itemStyle: { color: COLOR_BUY },
    symbol: 'pin',
    symbolSize: 38,
    label: { color: '#fff', fontSize: 10, fontWeight: 700 },
  }))
  const sellMarks = d.sell_points.map((p) => ({
    name: '卖出',
    coord: [p.date, p.price],
    value: '卖',
    itemStyle: { color: COLOR_SELL },
    symbol: 'pin',
    symbolSize: 38,
    label: { color: '#fff', fontSize: 10, fontWeight: 700 },
  }))

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
    {
      name: '收盘价', type: 'line', yAxisIndex: 2,
      data: d.close_prices, symbol: 'none', connectNulls: true,
      itemStyle: { color: COLOR_CLOSE }, lineStyle: { width: 1.5 },
      // 买卖标记点落在价格线上（价格穿越 MA 处）
      markPoint: {
        symbol: 'pin', symbolSize: 38,
        data: [...buyMarks, ...sellMarks],
        label: { fontSize: 10 },
      },
    },
    {
      name: 'MA120', type: 'line', yAxisIndex: 2,
      data: d.ma_values, symbol: 'none', connectNulls: true,
      itemStyle: { color: COLOR_MA }, lineStyle: { type: 'dashed', width: 1.5 },
    },
  ]
  const legendData = ['市值', '成本', '亏损', '盈利', '收益率', '收盘价', 'MA120']
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
        const close = d.close_prices[i]
        const ma = d.ma_values[i]
        const dev = d.price_vs_ma[i]
        const sig = d.signals[i]
        const hold = d.holding_shares[i]
        const mv = d.market_value[i]
        const cost = d.total_cost[i]
        const pnl = d.pnl[i]
        const rate = d.return_rate[i]
        const bench = d.benchmark_returns[i]
        const pnlColor = pnl >= 0 ? COLOR_UP : COLOR_DOWN
        const rateColor = rate >= 0 ? COLOR_UP : COLOR_DOWN
        const sigColor = sig === 'buy' ? COLOR_BUY : sig === 'sell' ? COLOR_SELL : tc.axisLabel
        const f2 = (v: number | null | undefined) => (v == null ? '-' : v.toFixed(2))
        const pt =
          sig === 'buy'
            ? d.buy_points.find((p) => p.date === d.dates[i])
            : sig === 'sell'
              ? d.sell_points.find((p) => p.date === d.dates[i])
              : undefined
        const amt = pt ? pt.amount : null
        const amtLabel = sig === 'buy' ? '买入金额' : sig === 'sell' ? '卖出金额' : ''
        return (
          `${d.dates[i]}` +
          (sig !== 'hold' ? `　<span style="color:${sigColor};font-weight:600">📌 ${SIGNAL_LABEL[sig]}</span>` : '') +
          (amt != null
            ? `<br/>${amtLabel}：<span style="color:${sigColor};font-weight:600">${amt.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>`
            : '') +
          `<br/>价格：${f2(close)}` +
          `<br/>MA120：<span style="color:${COLOR_MA}">${f2(ma)}</span>` +
          `　偏离：<span style="color:${dev != null && dev >= 0 ? COLOR_UP : COLOR_DOWN}">${dev == null ? '-' : dev.toFixed(2)}%</span>` +
          `<br/>持仓：${f2(hold)}` +
          `<br/>市值：${f2(mv)}　成本：${f2(cost)}` +
          `<br/>盈亏：<span style="color:${pnlColor};font-weight:600">${pnl >= 0 ? '+' : ''}${f2(pnl)}</span>` +
          `　收益率：<span style="color:${rateColor};font-weight:600">${f2(rate)}%</span>` +
          (hasBench && bench != null
            ? `<br/>${d.benchmark_name}：<span style="color:${COLOR_BENCH}">${f2(bench)}%</span>`
            : '')
        )
      },
    },
    legend: { data: legendData, top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 64, right: 120, top: 40, bottom: 64 },
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
      {
        type: 'value', name: '价格(元)', scale: true, position: 'right', offset: 56,
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
  <div class="chart-wrap">
    <div ref="el" class="chart"></div>
    <LegendHint />
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
