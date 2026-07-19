<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import type { EventImpactData } from '../api'
import { theme } from '../composables/useTheme'

// A 股配色：红涨绿跌
const COLOR_UP = '#ee6666'
const COLOR_DOWN = '#3ba272'
const COLOR_FLAT = '#9a9fa8'

const props = defineProps<{ data: EventImpactData | null; selected?: string | null }>()
const emit = defineEmits<{ (e: 'select', symbol: string): void }>()

const el = ref<HTMLDivElement>()
let chart: echarts.ECharts | null = null

function themeColors() {
  const dark = theme.value === 'dark'
  return {
    text: dark ? '#e8e8ec' : '#333333',
    label: dark ? '#a0a0a8' : '#6e7079',
    line: dark ? '#4a4a52' : '#c9cdd4',
  }
}

function colorOf(change: number | undefined): string {
  if (change == null) return COLOR_FLAT
  if (change > 0.01) return COLOR_UP
  if (change < -0.01) return COLOR_DOWN
  return COLOR_FLAT
}

function buildOption(d: EventImpactData): echarts.EChartsOption {
  const tc = themeColors()
  const changeOf: Record<string, number> = {}
  d.ranking.forEach((r) => (changeOf[r.symbol] = r.change_pct))

  const stages: { key: 'upstream' | 'midstream' | 'downstream'; label: string; x: number }[] = [
    { key: 'upstream', label: '上游', x: 120 },
    { key: 'midstream', label: '中游', x: 360 },
    { key: 'downstream', label: '下游', x: 600 },
  ]
  const nodes: any[] = []
  const links: any[] = []
  for (const st of stages) {
    const syms = d.chain_groups[st.key] || []
    const n = syms.length || 1
    syms.forEach((sym, i) => {
      const chg = changeOf[sym]
      const info = d.symbols_info.find((x) => x.symbol === sym)
      const name = info?.name || sym
      const y = 80 + ((n === 1 ? 160 : (300 * i) / (n - 1)))
      nodes.push({
        id: sym,
        name,
        symbolSize: Math.min(52, 22 + Math.abs(chg || 0) * 1.6),
        category: st.label,
        value: chg,
        x: st.x,
        y,
        itemStyle: { color: colorOf(chg) },
        label: { show: true, position: 'right', color: tc.text, fontSize: 11, formatter: () => `${name}\n${chg != null ? (chg >= 0 ? '+' : '') + chg.toFixed(1) + '%' : ''}` },
      })
    })
  }
  // 传导连线：上游→中游、中游→下游（每节点连到下一环节所有节点，低透明）
  const pairs: [string, string][] = []
  const up = d.chain_groups.upstream || []
  const mid = d.chain_groups.midstream || []
  const down = d.chain_groups.downstream || []
  up.forEach((u) => mid.forEach((m) => pairs.push([u, m])))
  mid.forEach((m) => down.forEach((dw) => pairs.push([m, dw])))
  for (const [s, t] of pairs) {
    links.push({ source: s, target: t, lineStyle: { color: tc.line, opacity: 0.22, width: 1, curveness: 0.1 } })
  }

  return {
    backgroundColor: 'transparent',
    tooltip: {
      formatter: (p: any) => {
        if (p.dataType === 'node') {
          const chg = p.data.value
          const c = colorOf(chg)
          return `<b>${p.data.name}</b> (${p.data.id})<br/>窗口涨跌：<b style="color:${c}">${chg != null ? (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%' : '无数据'}</b>`
        }
        return `${p.data.source} → ${p.data.target}`
      },
    },
    legend: [{ data: stages.map((s) => s.label), top: 4, textStyle: { color: tc.label, fontSize: 11 } }],
    series: [
      {
        type: 'graph',
        layout: 'none',
        categories: stages.map((s) => ({ name: s.label })),
        data: nodes,
        links,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: 7,
        roam: true,
        emphasis: {
          focus: 'adjacency',
          lineStyle: { width: 2, opacity: 0.7 },
          label: { fontWeight: 700 },
        },
        lineStyle: { color: tc.line, opacity: 0.22, curveness: 0.1 },
      },
    ],
  } as echarts.EChartsOption
}

function render() {
  if (!chart || !props.data) return
  chart.setOption(buildOption(props.data), true)
  // 选中高亮
  if (props.selected) {
    try {
      chart.dispatchAction({ type: 'focusNodeAdjacency', seriesIndex: 0, dataIndex: -1 })
    } catch { /* noop */ }
  }
}
function onResize() {
  chart?.resize()
}
function onClick(params: any) {
  if (params?.dataType === 'node' && params.data?.id) {
    emit('select', params.data.id)
  }
}
onMounted(() => {
  if (el.value) {
    chart = echarts.init(el.value)
    chart.on('click', onClick)
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
  <div ref="el" class="graph"></div>
</template>

<style scoped>
.graph {
  width: 100%;
  height: 420px;
}
</style>
