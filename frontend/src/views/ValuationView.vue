<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import MetricCard from '../components/MetricCard.vue'
import DateInput from '../components/DateInput.vue'
import ValuationChannelChart from '../components/ValuationChannelChart.vue'
import ValuationOverlayChart from '../components/ValuationOverlayChart.vue'
import {
  getValuationIndices,
  getSingleValuation,
  getOverlayValuation,
  type IndexItem,
  type OverlayData,
  type SingleValuationData,
  type ValuationLookback,
} from '../api'

type ViewMode = 'single' | 'overlay'

const viewMode = ref<ViewMode>('single')

// 指数下拉数据
const indices = ref<IndexItem[]>([])
const supportedIndices = computed(() => indices.value.filter((i) => i.supported))

// ---- 单指数视图 ----
const symbol = ref('000300')
const lookback = ref<ValuationLookback>('5y')
const startDate = ref('')
const endDate = ref('')
const singleData = ref<SingleValuationData | null>(null)
const singleLoading = ref(false)

// ---- 多指数叠加视图 ----
const overlayChecked = ref<Record<string, boolean>>({})
const overlayLookback = ref<ValuationLookback>('5y')
const overlayBase = ref<1 | 1000>(1)
const overlayData = ref<OverlayData | null>(null)
const overlayLoading = ref(false)

const errorMsg = ref('')

const LOOKBACK_OPTIONS: { value: ValuationLookback; label: string }[] = [
  { value: '1y', label: '近 1 年' },
  { value: '3y', label: '近 3 年' },
  { value: '5y', label: '近 5 年' },
  { value: '7y', label: '近 7 年' },
  { value: '10y', label: '近 10 年' },
  { value: 'all', label: '成立以来' },
]

// 分位 → 配色（<40 绿 / 40-60 灰 / 60-80 黄 / ≥80 红），与 016 温度计一致
function pctColor(p: number | null | undefined): string {
  if (p == null) return ''
  if (p >= 80) return '#ee6666'
  if (p >= 60) return '#faad14'
  if (p >= 40) return '#8a8f99'
  return '#3ba272'
}
function pctLabel(p: number | null | undefined): string {
  if (p == null) return '—'
  if (p >= 80) return '偏贵'
  if (p >= 60) return '中高'
  if (p >= 40) return '中性'
  return '偏便宜'
}
function posColor(pos: string): string {
  if (pos === '偏高估') return '#ee6666'
  if (pos === '中高') return '#faad14'
  if (pos === '中低') return '#8a8f99'
  if (pos === '偏低估') return '#3ba272'
  return ''
}

const sourceLabel = (t: string): string => {
  if (t === 'lg') return 'lg（乐咕乐股）'
  if (t === 'csindex') return 'csindex（中证指数公司）'
  return t
}

async function loadIndices() {
  try {
    const r = await getValuationIndices()
    if (r.code === 0) {
      indices.value = r.data.items
      // 默认勾选 沪深300 + 中证1000
      const init = ['000300', '000852']
      overlayChecked.value = Object.fromEntries(
        supportedIndices.value.map((i) => [i.index_code, init.includes(i.index_code)]),
      )
    }
  } catch {
    /* 下拉加载失败不阻断，下方查询会再次提示 */
  }
}

async function loadSingle() {
  errorMsg.value = ''
  singleLoading.value = true
  singleData.value = null
  try {
    const r = await getSingleValuation({
      symbol: symbol.value,
      lookback: lookback.value,
      start_date: startDate.value || undefined,
      end_date: endDate.value || undefined,
    })
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    singleData.value = r.data
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    singleLoading.value = false
  }
}

async function loadOverlay() {
  errorMsg.value = ''
  const picked = supportedIndices.value.filter((i) => overlayChecked.value[i.index_code])
  if (picked.length < 1) {
    errorMsg.value = '请至少勾选一个指数'
    return
  }
  overlayLoading.value = true
  overlayData.value = null
  try {
    const r = await getOverlayValuation({
      symbols: picked.map((i) => i.index_code),
      lookback: overlayLookback.value,
      base: overlayBase.value,
    })
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    overlayData.value = r.data
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    overlayLoading.value = false
  }
}

onMounted(async () => {
  await loadIndices()
  loadSingle()
})
</script>

<template>
  <section>
    <h1>估值看板</h1>
    <p class="muted">
      指数 PE 历史分位 + PE 估值通道：回答「现在贵不贵」。5 条通道线把历史 PE 分成高估/中性/低估区，
      当前 PE 落点一眼可见；多指数叠加看哪段估值修复更快。
    </p>

    <!-- 视图切换 -->
    <div class="view-tabs">
      <button :class="['tab', { active: viewMode === 'single' }]" @click="viewMode = 'single'">
        单指数估值
      </button>
      <button :class="['tab', { active: viewMode === 'overlay' }]" @click="viewMode = 'overlay'">
        多指数叠加
      </button>
    </div>

    <p v-if="errorMsg" class="err">{{ errorMsg }}</p>

    <!-- 单指数视图 -->
    <div v-if="viewMode === 'single'">
      <div class="form-card">
        <div class="form-row">
          <label class="index-label">
            指数
            <select v-model="symbol">
              <option
                v-for="i in indices"
                :key="i.index_code"
                :value="i.index_code"
                :disabled="!i.supported"
                :title="i.supported ? '' : i.note || '该指数暂不支持'"
              >
                {{ i.name_cn }}（{{ i.index_code }}）{{ i.supported ? '' : ' · 不支持' }}
              </option>
            </select>
          </label>
          <label>
            时间窗口
            <select v-model="lookback">
              <option v-for="o in LOOKBACK_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>
          <label>
            起始日期（可选）
            <DateInput v-model="startDate" />
          </label>
          <label>
            结束日期（可选）
            <DateInput v-model="endDate" />
          </label>
          <button :disabled="singleLoading" class="primary" @click="loadSingle">
            {{ singleLoading ? '加载中…' : '查询' }}
          </button>
        </div>
      </div>

      <template v-if="singleData?.available">
        <div class="cards">
          <MetricCard label="当前 PE" :value="singleData.current_pe != null ? singleData.current_pe.toFixed(2) : '—'" />
          <MetricCard
            label="历史分位"
            :value="(singleData.percentile ?? 0) + '%  ' + pctLabel(singleData.percentile)"
            :color="pctColor(singleData.percentile)"
          />
          <MetricCard
            label="通道位置"
            :value="singleData.channel_position"
            :color="posColor(singleData.channel_position)"
          />
          <MetricCard
            label="PB"
            :value="singleData.pb_available && singleData.current_pb != null ? singleData.current_pb.toFixed(2) : '—'"
            :hint="singleData.source_type === 'csindex' ? '该指数无 PB 数据' : undefined"
          />
          <MetricCard
            label="股息率"
            :value="singleData.dividend_available && singleData.dividend_yield != null ? singleData.dividend_yield.toFixed(2) + '%' : '—'"
            :hint="singleData.source_type === 'csindex' ? '仅当日快照，无历史分位' : undefined"
          />
        </div>

        <div class="chart-card">
          <h3>
            {{ singleData.name_cn }}（{{ singleData.index_code }}）· PE 估值通道
            <span class="src-tag">{{ sourceLabel(singleData.source_type) }}</span>
          </h3>
          <ValuationChannelChart :data="singleData" />
        </div>
        <p class="muted">
          数据源：{{ sourceLabel(singleData.source_type) }} · 截至 {{ singleData.as_of }}
          <span v-if="singleData.fetch_warning"> · ⚠ {{ singleData.fetch_warning }}</span>
        </p>
      </template>

      <p v-else-if="singleData && !singleData.available" class="warn">
        {{ singleData.note || '该指数暂无估值数据' }}
      </p>
    </div>

    <!-- 多指数叠加视图 -->
    <div v-else>
      <div class="form-card">
        <div class="form-row check-row">
          <span class="check-title">选择指数：</span>
          <label v-for="i in supportedIndices" :key="i.index_code" class="check">
            <input type="checkbox" v-model="overlayChecked[i.index_code]" />
            {{ i.name_cn }}（{{ i.index_code }}）
          </label>
        </div>
        <div class="form-row">
          <label>
            时间窗口
            <select v-model="overlayLookback">
              <option v-for="o in LOOKBACK_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
            </select>
          </label>
          <label>
            归一化基准
            <select v-model.number="overlayBase">
              <option :value="1">第 1 天 = 1</option>
              <option :value="1000">第 1 天 = 1000</option>
            </select>
          </label>
          <button :disabled="overlayLoading" class="primary" @click="loadOverlay">
            {{ overlayLoading ? '加载中…' : '查询' }}
          </button>
        </div>
      </div>

      <template v-if="overlayData && overlayData.series.length">
        <div class="chart-card">
          <h3>多指数估值叠加（PE-TTM 归一化，起点 = {{ overlayData.base }}）</h3>
          <ValuationOverlayChart :data="overlayData" />
        </div>
      </template>
      <p v-else-if="overlayData && overlayData.note" class="warn">{{ overlayData.note }}</p>
    </div>
  </section>
</template>

<style scoped>
.muted {
  color: var(--text-tertiary);
  font-size: 13px;
}
.view-tabs {
  display: flex;
  gap: 8px;
  margin: 12px 0 4px;
}
.tab {
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 8px 18px;
  font-size: 14px;
  cursor: pointer;
  color: var(--text-secondary);
}
.tab.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
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
  margin-bottom: 12px;
}
.form-row:last-child {
  margin-bottom: 0;
}
.check-row {
  align-items: center;
}
.check-title {
  font-size: 13px;
  color: var(--text-secondary);
}
.check {
  display: inline-flex;
  flex-direction: row;
  align-items: center;
  gap: 5px;
  font-size: 14px;
  color: var(--text);
  cursor: pointer;
}
label {
  display: flex;
  flex-direction: column;
  font-size: 13px;
  color: var(--text-secondary);
  gap: 4px;
}
.index-label select {
  min-width: 220px;
}
select,
input[type='text'] {
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  font-size: 14px;
  min-width: 150px;
  background: var(--input-bg);
  color: var(--text);
}
select option:disabled {
  color: var(--text-tertiary);
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
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin: 16px 0;
}
.chart-card {
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 16px 20px;
  background: var(--surface);
}
.chart-card h3 {
  margin: 0 0 8px;
  font-size: 16px;
}
.src-tag {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-tertiary);
  margin-left: 8px;
}
.warn {
  color: #b8860b;
  background: color-mix(in srgb, #faad14 12%, transparent);
  border: 1px solid color-mix(in srgb, #faad14 30%, transparent);
  border-radius: 6px;
  padding: 8px 12px;
}
.err {
  color: var(--error-text);
  background: var(--error-bg);
  border: 1px solid var(--error-border);
  border-radius: 6px;
  padding: 8px 12px;
}
</style>
