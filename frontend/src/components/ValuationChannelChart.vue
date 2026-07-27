<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import LegendHint from './LegendHint.vue'
import type { SingleValuationData } from '../api'
import { theme } from '../composables/useTheme'

// PE 高=贵用红，PE 低=便宜用绿（与温度计配色一致，不套用红涨绿跌）
const COLOR_PE = '#5470c6' // PE 主折线（蓝）
const COLOR_PB = '#fac858' // PB 折线（金，右轴）
const COLOR_HI = '#ee6666' // 高估区（红）
const COLOR_LO = '#3ba272' // 低估区（绿）
const COLOR_MED = '#faad14' // 中位线（黄）
const COLOR_NOW = '#ee6666' // 当前点（红，醒目）

const props = defineProps<{ data: SingleValuationData | null }>()

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

function buildYAxis(tc: ReturnType<typeof themeColors>, hasPb: boolean) {
  const yAxis: Record<string, unknown>[] = [
    {
      type: 'value',
      name: 'PE',
      scale: true,
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { lineStyle: { color: tc.splitLine } },
      nameTextStyle: { color: tc.axisLabel },
    },
  ]
  if (hasPb) {
    yAxis.push({
      type: 'value',
      name: 'PB',
      scale: true,
      position: 'right',
      axisLine: { show: true, lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      splitLine: { show: false },
      nameTextStyle: { color: tc.axisLabel },
    })
  }
  return yAxis as NonNullable<echarts.EChartsOption['yAxis']>
}

function buildOption(d: SingleValuationData): echarts.EChartsOption {
  const tc = themeColors()
  const ch = d.channel
  const hasChannel = !!ch && 'l1_min' in ch
  const hasPb = d.pb_available && d.pb.some((v) => v != null)

  const legendData = ['PE-TTM']
  if (hasPb) legendData.push('PB')

  const series: echarts.SeriesOption[] = [
    {
      name: 'PE-TTM',
      type: 'line',
      yAxisIndex: 0,
      data: d.pe_ttm,
      symbol: 'none',
      smooth: true,
      connectNulls: false,
      itemStyle: { color: COLOR_PE },
      lineStyle: { width: 2 },
      ...(hasChannel
        ? {
            markLine: {
              symbol: 'none',
              silent: true,
              label: { fontSize: 10, position: 'insideEndTop' },
              data: [
                { yAxis: ch.l5_max, lineStyle: { color: COLOR_HI, type: 'dashed' }, label: { formatter: '极高', color: COLOR_HI } },
                { yAxis: ch.l4_high, lineStyle: { color: COLOR_HI, type: 'dotted', opacity: 0.7 }, label: { formatter: '偏高', color: COLOR_HI } },
                { yAxis: ch.l3_median, lineStyle: { color: COLOR_MED, type: 'dashed' }, label: { formatter: '中位', color: COLOR_MED } },
                { yAxis: ch.l2_low, lineStyle: { color: COLOR_LO, type: 'dotted', opacity: 0.7 }, label: { formatter: '偏低', color: COLOR_LO } },
                { yAxis: ch.l1_min, lineStyle: { color: COLOR_LO, type: 'dashed' }, label: { formatter: '极低', color: COLOR_LO } },
              ],
            },
            markArea: {
              silent: true,
              itemStyle: { color: 'transparent' },
              data: [
                [{ yAxis: ch.l4_high, itemStyle: { color: 'rgba(238,102,102,0.10)' } }, { yAxis: ch.l5_max }],
                [{ yAxis: ch.l1_min, itemStyle: { color: 'rgba(59,162,114,0.10)' } }, { yAxis: ch.l2_low }],
              ],
            },
            markPoint: {
              symbol: 'circle',
              symbolSize: 12,
              data:
                d.current_pe != null && d.dates.length
                  ? [
                      {
                        name: '现在',
                        coord: [d.dates[d.dates.length - 1], d.current_pe],
                        value: '现在',
                        itemStyle: { color: COLOR_NOW, borderColor: '#fff', borderWidth: 2 },
                        label: { formatter: '现在', color: COLOR_NOW, position: 'top', fontSize: 11, fontWeight: 700 },
                      },
                    ]
                  : [],
            },
          }
        : {}),
    },
  ]

  if (hasPb) {
    series.push({
      name: 'PB',
      type: 'line',
      yAxisIndex: 1,
      data: d.pb,
      symbol: 'none',
      connectNulls: true,
      itemStyle: { color: COLOR_PB },
      lineStyle: { width: 1.5, type: 'dashed' },
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
        const pe = d.pe_ttm[i]
        const pb = d.pb[i]
        const pos = d.channel_position
        const posColor = pos === '偏高估' ? COLOR_HI : pos === '偏低估' ? COLOR_LO : tc.axisLabel
        const f2 = (v: number | null | undefined) => (v == null ? '—' : v.toFixed(2))
        const pctColor = d.percentile == null ? tc.axisLabel : d.percentile >= 60 ? COLOR_HI : d.percentile >= 40 ? tc.axisLabel : COLOR_LO
        return (
          `${d.dates[i]}` +
          `<br/>PE-TTM：<span style="font-weight:600">${f2(pe)}</span>` +
          (d.percentile != null ? `　分位：<span style="color:${pctColor};font-weight:600">${d.percentile}%</span>` : '') +
          `<br/>通道：<span style="color:${posColor};font-weight:600">${pos}</span>` +
          (hasPb ? `<br/>PB：<span style="color:${COLOR_PB}">${f2(pb)}</span>` : '') +
          (d.dividend_yield != null ? `<br/>股息率：<span style="color:${COLOR_LO}">${f2(d.dividend_yield)}%</span>` : '')
        )
      },
    },
    legend: { data: legendData, top: 0, textStyle: { color: tc.axisLabel } },
    grid: { left: 60, right: hasPb ? 64 : 36, top: 40, bottom: 64 },
    xAxis: {
      type: 'category',
      data: d.dates,
      boundaryGap: true,
      axisLine: { lineStyle: { color: tc.axisLine } },
      axisLabel: { color: tc.axisLabel },
      axisTick: { lineStyle: { color: tc.axisLine } },
    },
    yAxis: buildYAxis(tc, hasPb),
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
    <LegendHint text="红线=高估区，绿线=低估区；●为当前 PE。点击图例隐藏 PB" />
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
