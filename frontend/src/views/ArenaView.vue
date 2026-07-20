<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import ArenaNavChart from '../components/ArenaNavChart.vue'
import DateInput from '../components/DateInput.vue'
import ArenaTable from '../components/ArenaTable.vue'
import { compareArena, searchSymbols, type ArenaData, type SymbolItem } from '../api'

type Mode = 'cross_strategy' | 'cross_symbol'

const mode = ref<Mode>('cross_strategy')
// cross_strategy：单标的
const symbol = ref('512890')
const symbolSuggest = ref<SymbolItem[]>([])
let debounce: ReturnType<typeof setTimeout> | undefined
// cross_symbol：固定策略 + 多标的
const strategy = ref<'dca' | 'ma120' | 'drawboard' | 'grid'>('ma120')
const symbols = ref<string[]>(['510880', '512890', '510300'])
const symbolInput = ref('')

const startDate = ref('')
const endDate = ref('')
const loading = ref(false)
const errorMsg = ref('')
const arenaData = ref<ArenaData | null>(null)

function onSymbolInput() {
  clearTimeout(debounce)
  const q = symbol.value.trim().replace(/^(sh|sz|bj)/i, '')
  if (!q) {
    symbolSuggest.value = []
    return
  }
  debounce = setTimeout(async () => {
    try {
      const r = await searchSymbols(q)
      symbolSuggest.value = r.code === 0 ? r.data : []
    } catch {
      symbolSuggest.value = []
    }
  }, 250)
}

function addSymbol() {
  const c = symbolInput.value.trim().replace(/^(sh|sz|bj)/i, '')
  if (/^\d{6}$/.test(c) && !symbols.value.includes(c)) {
    symbols.value.push(c)
    symbolInput.value = ''
  }
}
function removeSymbol(i: number) {
  symbols.value.splice(i, 1)
}

const STRATEGY_LABEL: Record<string, string> = {
  dca: '定投', ma120: 'MA120', drawboard: '回撤买入', grid: '网格交易',
}

// ArenaNavChart 的 series：每对比项一条归一化净值曲线
const navSeries = computed(() => {
  if (!arenaData.value) return []
  return arenaData.value.items
    .filter((it) => arenaData.value!.nav_series[it.task_id])
    .map((it) => {
      const ns = arenaData.value!.nav_series[it.task_id]
      return {
        name: `${it.symbol_name || it.symbol}·${STRATEGY_LABEL[it.strategy] || it.strategy}`,
        dates: ns.dates,
        nav: ns.nav,
      }
    })
})

async function runCompare() {
  errorMsg.value = ''
  arenaData.value = null
  loading.value = true
  try {
    const r = await compareArena({
      mode: mode.value,
      symbol: mode.value === 'cross_strategy' ? symbol.value.trim().replace(/^(sh|sz|bj)/i, '') : undefined,
      strategy: mode.value === 'cross_symbol' ? strategy.value : undefined,
      symbols: mode.value === 'cross_symbol' ? symbols.value : undefined,
      start: startDate.value || undefined,
      end: endDate.value || undefined,
    })
    if (r.code !== 0) {
      errorMsg.value = r.message
    } else {
      arenaData.value = r.data
      if (!r.data.items.length) errorMsg.value = '没有匹配的回测记录（先在各策略页跑一些回测）'
    }
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  runCompare() // 进入即用默认参数对比；改参数后点「对比」重跑
})
</script>

<template>
  <section>
    <h1>策略擂台</h1>
    <p class="muted">横向对比：同标的多策略，或同策略多标的。消费已跑过的回测结果。</p>

    <div class="form-card">
      <div class="mode-row">
        <label class="radio"><input v-model="mode" type="radio" value="cross_strategy" /> 同标的多策略</label>
        <label class="radio"><input v-model="mode" type="radio" value="cross_symbol" /> 同策略多标的</label>
      </div>

      <div class="form-row">
        <label v-if="mode === 'cross_strategy'" class="symbol-label">
          标的代码
          <input v-model="symbol" list="arena-suggest" placeholder="如 512890" @input="onSymbolInput" />
          <datalist id="arena-suggest">
            <option v-for="s in symbolSuggest" :key="s.code" :value="s.code">{{ s.name }}</option>
          </datalist>
        </label>

        <template v-else>
          <label>
            策略
            <select v-model="strategy">
              <option value="dca">定投</option>
              <option value="ma120">MA120</option>
              <option value="drawboard">回撤买入</option>
              <option value="grid">网格交易</option>
            </select>
          </label>
          <label class="symbol-label">
            添加标的
            <div class="symbol-field">
              <input v-model="symbolInput" placeholder="如 510880" @keydown.enter="addSymbol" />
              <button class="add-btn" type="button" @click="addSymbol">＋</button>
            </div>
          </label>
        </template>

        <label>起始(可选)<DateInput v-model="startDate" /></label>
        <label>结束(可选)<DateInput v-model="endDate" /></label>
        <button :disabled="loading" class="primary" @click="runCompare">
          {{ loading ? '对比中…' : '对比' }}
        </button>
      </div>

      <div v-if="mode === 'cross_symbol'" class="chips">
        <span v-for="(s, i) in symbols" :key="s" class="chip">
          {{ s }}<button class="chip-x" type="button" @click="removeSymbol(i)">×</button>
        </span>
        <span v-if="!symbols.length" class="muted">请添加至少 1 个标的</span>
      </div>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

    <div v-if="arenaData && arenaData.items.length" class="chart-card">
      <h3>归一化净值对比（起点=100）</h3>
      <ArenaNavChart :series="navSeries" />
    </div>

    <div v-if="arenaData && arenaData.items.length" class="chart-card">
      <h3>指标对比（绿色=该行最优）</h3>
      <ArenaTable :items="arenaData.items" />
    </div>
  </section>
</template>

<style scoped>
.muted { color: var(--text-tertiary); font-size: 13px; }
.form-card { border: 1px solid var(--border-light); border-radius: 8px; padding: 16px 20px; background: var(--surface); margin: 16px 0; }
.mode-row { display: flex; gap: 20px; margin-bottom: 12px; }
.radio { display: flex; flex-direction: row; align-items: center; gap: 6px; font-size: 14px; color: var(--text); }
.form-row { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-end; }
label { display: flex; flex-direction: column; font-size: 13px; color: var(--text-secondary); gap: 4px; }
.symbol-label { min-width: 240px; }
.symbol-field { display: flex; align-items: center; gap: 8px; }
input, select { padding: 8px 10px; border: 1px solid var(--input-border); border-radius: 6px; font-size: 14px; min-width: 130px; background: var(--input-bg); color: var(--text); }
.symbol-field input, .symbol-label input { min-width: 160px; }
.add-btn { background: var(--primary); color: #fff; border: none; border-radius: 6px; width: 36px; height: 36px; font-size: 18px; cursor: pointer; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.chip { background: color-mix(in srgb, var(--primary) 14%, transparent); color: var(--primary); border-radius: 14px; padding: 3px 10px; font-size: 13px; display: inline-flex; align-items: center; gap: 6px; }
.chip-x { background: none; border: none; color: inherit; cursor: pointer; font-size: 15px; line-height: 1; }
button.primary { background: var(--primary); color: #fff; border: none; border-radius: 6px; padding: 9px 22px; font-size: 14px; cursor: pointer; height: 38px; }
button.primary:disabled { background: var(--primary-disabled); cursor: not-allowed; }
.chart-card { border: 1px solid var(--border-light); border-radius: 8px; padding: 16px 20px; background: var(--surface); margin: 16px 0; }
.chart-card h3 { margin: 0 0 8px; font-size: 16px; }
.err { color: var(--error-text); background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 6px; padding: 8px 12px; }
</style>
