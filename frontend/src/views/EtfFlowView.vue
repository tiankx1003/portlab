<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import * as echarts from 'echarts'
import { getEtfFlow, type EtfFlowData, type EtfSignal } from '../api'

// 信号展示元数据（顺序即卡片顺序）
const SIGNAL_META: { key: string; name: string; unit: string; type: 'bar' | 'line' }[] = [
  { key: 'shares_change', name: '份额变动', unit: '万份', type: 'bar' },
  { key: 'northbound', name: '北向资金净流入', unit: '万元', type: 'line' },
  { key: 'main_flow', name: '主力资金净流入', unit: '万元', type: 'bar' },
]

const symbol = ref('510880')
const startDate = ref('2024-01-01')
const endDate = ref(new Date().toISOString().slice(0, 10))
const loading = ref(false)
const errorMsg = ref('')
const data = ref<EtfFlowData | null>(null)

// 每个信号一个 chart 实例（按 key 存）
const chartEls = ref<Record<string, HTMLDivElement | null>>({})
const charts: Record<string, echarts.ECharts> = {}

async function load() {
  loading.value = true
  errorMsg.value = ''
  data.value = null
  try {
    const r = await getEtfFlow(symbol.value, startDate.value, endDate.value)
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    data.value = r.data
    await nextTick()
    renderAll()
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function renderAll() {
  if (!data.value) return
  for (const meta of SIGNAL_META) {
    const sig: EtfSignal | undefined = data.value.signals[meta.key]
    const el = chartEls.value[meta.key]
    if (!el) continue
    if (!sig?.available || !sig.dates) continue
    if (!charts[meta.key]) charts[meta.key] = echarts.init(el)
    const pos = sig.values!.map((v) => v >= 0)
    charts[meta.key].setOption(
      {
        title: { text: `${meta.name}（${meta.unit}）`, left: 8, top: 4, textStyle: { fontSize: 13 } },
        tooltip: { trigger: 'axis' },
        grid: { left: 60, right: 20, top: 36, bottom: 28 },
        xAxis: { type: 'category', data: sig.dates, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { fontSize: 10 } },
        series: [
          {
            type: meta.type,
            data: sig.values!.map((v, i) => ({
              value: v,
              itemStyle: { color: pos[i] ? '#ee6666' : '#3ba272' }, // 红正绿负
            })),
            lineStyle: meta.type === 'line' ? { color: '#1f6feb', width: 1.5 } : undefined,
            itemStyle: meta.type === 'line' ? { color: '#1f6feb' } : undefined,
          },
        ],
      } as echarts.EChartsOption,
      true,
    )
  }
}

const resize = () => Object.values(charts).forEach((c) => c.resize())

onMounted(() => {
  load()
  window.addEventListener('resize', resize)
})
onUnmounted(() => {
  window.removeEventListener('resize', resize)
  Object.values(charts).forEach((c) => c.dispose())
})
</script>

<template>
  <section>
    <h1>ETF 资金流向</h1>
    <p class="muted">
      三信号（Tushare）：份额变动（机构/国家队申赎）+ 北向资金（外资）+ 主力资金。ETF 主力资金 Tushare 未覆盖，仅展示前两项。
    </p>

    <div class="form-card">
      <div class="form-row">
        <label>
          标的代码
          <input v-model="symbol" />
        </label>
        <label>
          起始日期
          <input v-model="startDate" type="date" />
        </label>
        <label>
          结束日期
          <input v-model="endDate" type="date" />
        </label>
        <button :disabled="loading" class="primary" @click="load">
          {{ loading ? '加载中…' : '加载' }}
        </button>
      </div>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>
    <p v-if="data && !data.available" class="err">无可用信号数据（请确认 Tushare 开关已开启且 Token 有效）。</p>

    <template v-for="meta in SIGNAL_META" :key="meta.key">
      <div v-if="data?.signals[meta.key]" class="signal-card">
        <div
          v-if="data.signals[meta.key].available"
          :ref="(el) => (chartEls[meta.key] = el as HTMLDivElement | null)"
          class="chart"
        ></div>
        <p v-else class="signal-unavailable">
          {{ meta.name }}：{{ data.signals[meta.key].reason }}
        </p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.muted {
  color: var(--text-tertiary);
  font-size: 13px;
  margin: 4px 0 0;
}
.form-card {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 16px 20px;
  background: var(--surface);
  margin: 16px 0;
}
.form-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 13px;
  color: var(--text-secondary);
  gap: 4px;
}
input {
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  font-size: 14px;
  min-width: 140px;
  background: var(--input-bg);
  color: var(--text);
}
button.primary {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 9px 22px;
  font-size: 14px;
  cursor: pointer;
  height: 38px;
}
button.primary:disabled {
  background: var(--primary-disabled);
  cursor: not-allowed;
}
.signal-card {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 8px;
  background: var(--surface);
  margin-bottom: 16px;
}
.chart {
  width: 100%;
  height: 280px;
}
.signal-unavailable {
  padding: 18px;
  color: var(--text-tertiary);
  font-size: 13px;
  text-align: center;
}
.err {
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
