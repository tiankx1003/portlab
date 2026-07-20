<script setup lang="ts">
import type { StrategyResultItem } from '../api'

const props = defineProps<{ items: StrategyResultItem[] }>()

// 指标行：higherBetter=true 取最大为最优（收益类，红色高亮）；false 取最小（回撤类，绿色）
const metrics: {
  label: string
  get: (it: StrategyResultItem) => number | null
  higherBetter: boolean
  colorize?: (v: number) => string
}[] = [
  { label: '总收益率 %', get: (i) => i.total_return_rate, higherBetter: true },
  { label: '年化 %', get: (i) => i.annualized_return, higherBetter: true },
  { label: '最大回撤 %', get: (i) => i.max_drawdown, higherBetter: false },
  { label: '夏普', get: (i) => i.sharpe, higherBetter: true },
]

function bestIdx(get: (it: StrategyResultItem) => number | null, higherBetter: boolean): number {
  let bi = -1
  let bv: number | null = null
  props.items.forEach((it, i) => {
    const v = get(it)
    if (v == null) return
    if (bv == null || (higherBetter ? v > bv : v < bv)) {
      bv = v
      bi = i
    }
  })
  return bi
}

function fmt(n: number | null, d = 2): string {
  if (n == null || Number.isNaN(n)) return '-'
  return n.toLocaleString('zh-CN', { minimumFractionDigits: d, maximumFractionDigits: d })
}
</script>

<template>
  <div class="arena-table-wrap">
    <table class="arena-table">
      <thead>
        <tr>
          <th>指标</th>
          <th v-for="(it, i) in items" :key="it.task_id">
            <span class="col-name">{{ it.symbol_name || it.symbol }}</span>
            <span class="col-strat">{{ it.strategy }}</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="m in metrics" :key="m.label">
          <td class="metric-label">{{ m.label }}</td>
          <td
            v-for="(it, i) in items"
            :key="it.task_id"
            :class="{ best: bestIdx(m.get, m.higherBetter) === i }"
          >
            <span :class="m.label.includes('回撤') ? 'neg' : m.get(it) != null && m.get(it)! >= 0 ? 'pos' : 'neg'">
              {{ fmt(m.get(it)) }}
            </span>
          </td>
        </tr>
        <tr>
          <td class="metric-label">买/卖 次数</td>
          <td v-for="it in items" :key="it.task_id">
            <span class="num-buy">{{ it.buy_count }}</span> / <span class="num-sell">{{ it.sell_count }}</span>
          </td>
        </tr>
        <tr>
          <td class="metric-label">参数</td>
          <td v-for="it in items" :key="it.task_id" class="params">{{ it.params_summary }}</td>
        </tr>
        <tr>
          <td class="metric-label">区间</td>
          <td v-for="it in items" :key="it.task_id" class="period">{{ it.start_date }} ~ {{ it.end_date }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<style scoped>
.arena-table-wrap {
  overflow-x: auto;
}
.arena-table {
  border-collapse: collapse;
  width: 100%;
  font-size: 13px;
}
.arena-table th,
.arena-table td {
  border: 1px solid var(--border-light);
  padding: 8px 10px;
  text-align: center;
  white-space: nowrap;
}
.arena-table th {
  background: var(--surface);
  color: var(--text-secondary);
  font-weight: 600;
}
.col-name { display: block; color: var(--text); font-weight: 600; }
.col-strat { font-size: 11px; color: var(--text-tertiary); text-transform: uppercase; }
.metric-label { text-align: left; color: var(--text-secondary); background: var(--surface); }
td.best { background: color-mix(in srgb, #3ba272 18%, transparent); font-weight: 700; }
.pos { color: #ee6666; }
.neg { color: #3ba272; }
.num-buy { color: #ee6666; font-weight: 600; }
.num-sell { color: #3a7afe; font-weight: 600; }
.params, .period { font-size: 12px; color: var(--text-secondary); }
</style>
