<script setup lang="ts">
import { onMounted, ref } from 'vue'
import SignalCard from '../components/SignalCard.vue'
import ResonanceSummary from '../components/ResonanceSummary.vue'
import EquityBondChart from '../components/EquityBondChart.vue'
import MeanAnchorChart from '../components/MeanAnchorChart.vue'
import ValuationChannelChart from '../components/ValuationChannelChart.vue'
import {
  getResonance,
  getValuationIndices,
  type IndexItem,
  type ResonanceData,
  type SingleValuationData,
} from '../api'

// 控件
const indices = ref<IndexItem[]>([])
const symbol = ref('000300')
const lookback = ref('5y')
const loading = ref(false)
const errorMsg = ref('')

const LOOKBACK_OPTIONS = [
  { value: '1y', label: '近 1 年' },
  { value: '3y', label: '近 3 年' },
  { value: '5y', label: '近 5 年' },
  { value: '10y', label: '近 10 年' },
]

// 数据
const data = ref<ResonanceData | null>(null)
// PE 通道图需要 SingleValuationData 格式，从 target.pe_channel_chart 转换
const peChannelData = ref<SingleValuationData | null>(null)

async function loadIndices() {
  try {
    const r = await getValuationIndices()
    if (r.code === 0) indices.value = r.data.items.filter((i) => i.supported)
  } catch {
    /* 静默 */
  }
}

async function load() {
  errorMsg.value = ''
  loading.value = true
  data.value = null
  peChannelData.value = null
  try {
    const r = await getResonance(symbol.value, lookback.value)
    if (r.code !== 0) {
      errorMsg.value = r.message
      return
    }
    data.value = r.data
    // 转换 PE 通道图数据 → ValuationChannelChart 需要的 SingleValuationData
    const t = r.data.target
    if (t.pe_channel_chart && t.pe_channel_chart.dates.length) {
      const ch = t.pe_channel_chart.series.channel || {}
      peChannelData.value = {
        available: true,
        index_code: t.resolved_index || t.symbol,
        name_cn: t.name_cn,
        source_type: 'lg',
        supported: true,
        dates: t.pe_channel_chart.dates,
        pe_ttm: t.pe_channel_chart.series.pe_ttm || [],
        pb: t.pe_channel_chart.series.pb || [],
        channel: ch,
        current_pe: (t.pe_channel_chart.series.pe_ttm || []).filter((v) => v != null).slice(-1)[0] ?? null,
        percentile: t.metrics.find((m) => m.key === 'pe')?.value ?? null,
        channel_position: '—',
        current_pb: (t.pe_channel_chart.series.pb || []).filter((v) => v != null).slice(-1)[0] ?? null,
        dividend_yield: t.metrics.find((m) => m.key === 'dividend')?.value ?? null,
        pb_available: (t.pe_channel_chart.series.pb || []).some((v) => v != null),
        dividend_available: t.metrics.find((m) => m.key === 'dividend')?.value != null,
        as_of: t.as_of,
      } as SingleValuationData
    }
  } catch (e) {
    errorMsg.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadIndices()
  load()
})
</script>

<template>
  <section>
    <h1>估值与信号看板</h1>
    <p class="muted">
      三层共振：技术估值 + 大类资产 + 资金宏观。全绿=历史底部区域，全红=历史顶部，其余=保持纪律。
      体温计，不是交易台——只呈现状态，不输出买卖指令。
    </p>

    <!-- 控件栏 -->
    <div class="form-card">
      <div class="form-row">
        <label>标的</label>
        <select v-model="symbol" @change="load">
          <option v-for="i in indices" :key="i.index_code" :value="i.index_code">
            {{ i.name_cn }}（{{ i.index_code }}）
          </option>
          <option value="512890">红利低波100（512890）</option>
          <option value="510880">上证红利（510880）</option>
          <option value="513920">港股央企红利（513920）</option>
        </select>
        <label>窗口</label>
        <select v-model="lookback" @change="load">
          <option v-for="o in LOOKBACK_OPTIONS" :key="o.value" :value="o.value">{{ o.label }}</option>
        </select>
        <button class="primary" :disabled="loading" @click="load">
          {{ loading ? '查询中…' : '查询' }}
        </button>
        <span v-if="data?.as_of" class="as-of">数据截至 {{ data.as_of }}</span>
      </div>
    </div>

    <p v-if="errorMsg" class="error">{{ errorMsg }}</p>

    <template v-if="data">
      <!-- 三层共振汇总 -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">三层共振汇总</h2>
        </div>
        <ResonanceSummary
          :layer1="data.layer1"
          :layer2="data.layer2"
          :layer3="data.layer3"
          :overall="data.overall_status"
          :advice="data.action_advice"
        />
      </div>

      <!-- 第一层：技术 + 估值 -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">第一层：技术 + 估值</h2>
          <span class="block-sub">{{ data.target.name_cn }}（{{ data.target.symbol }}）</span>
        </div>
        <div v-if="data.target.warning" class="warn">{{ data.target.warning }}</div>
        <div class="cards">
          <SignalCard v-for="m in data.target.metrics" :key="m.key" :item="m" />
        </div>
        <div v-if="peChannelData" class="chart-block">
          <h3 class="chart-title">PE 历史通道</h3>
          <ValuationChannelChart :data="peChannelData" />
        </div>
        <div v-if="data.target.equity_bond_chart" class="chart-block">
          <h3 class="chart-title">股债比价通道</h3>
          <EquityBondChart :data="data.target.equity_bond_chart" />
        </div>
      </div>

      <!-- 第二层：大类资产估值 -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">第二层：大类资产估值</h2>
        </div>
        <div v-if="data.market.warning" class="warn">{{ data.market.warning }}</div>
        <div class="cards">
          <SignalCard v-for="m in data.market.metrics" :key="m.key" :item="m" />
        </div>
        <div v-if="data.market.mean_anchor_chart" class="chart-block">
          <h3 class="chart-title">沪深300全收益 vs 5年均线</h3>
          <MeanAnchorChart :data="data.market.mean_anchor_chart" />
        </div>
        <div v-if="data.market.equity_bond_chart" class="chart-block">
          <h3 class="chart-title">沪深300 股债比价通道</h3>
          <EquityBondChart :data="data.market.equity_bond_chart" />
        </div>
      </div>

      <!-- 第三层：资金 + 宏观 -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">第三层：资金 + 宏观</h2>
        </div>
        <div v-if="data.macro.warning" class="warn">{{ data.macro.warning }}</div>
        <div v-if="data.macro.metrics.length" class="cards">
          <SignalCard v-for="m in data.macro.metrics" :key="m.key" :item="m" />
        </div>
        <p v-else class="muted">配置 Tushare Token 后可查看资金/宏观信号（社融/M1M2/PMI/PPI/融资融券/北向）。</p>
      </div>

      <!-- 底部数据缺口提示 -->
      <div class="gap-notice">
        <div class="gap-title">⚠ 本看板部分指标受数据源限制，当前为降级展示：</div>
        <ul>
          <li>股息率：仅当日快照，无法算历史分位（缺历史序列源）</li>
          <li>红利指数 PB：无数据源，灰显</li>
          <li>万得基金指数（股基/债基相对强弱）：Wind 私有，未展示</li>
          <li>北向资金：2024-08 后改为总额披露，精度下降</li>
        </ul>
        <p class="muted">完整替代方案见任务文档「032 → 开放问题 → 替代数据源调研」</p>
      </div>
    </template>

    <p v-else-if="!loading && !errorMsg" class="muted">点击「查询」加载数据。</p>
  </section>
</template>

<style scoped>
.muted {
  color: var(--text-tertiary);
  font-size: 13px;
}
.error {
  color: #ee6666;
  font-size: 13px;
  margin: 12px 0;
}
.warn {
  color: #faad14;
  font-size: 12px;
  margin: 8px 0;
  padding: 6px 10px;
  background: rgba(250, 173, 20, 0.08);
  border-radius: 6px;
}
.form-card {
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 14px 18px;
  margin: 16px 0;
}
.form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.form-row label {
  font-size: 13px;
  color: var(--text-secondary);
}
.form-row select {
  padding: 6px 10px;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  background: var(--surface);
  color: var(--text-primary);
  font-size: 13px;
}
button.primary {
  padding: 7px 18px;
  border: none;
  border-radius: 6px;
  background: var(--accent, #5470c6);
  color: #fff;
  font-size: 13px;
  cursor: pointer;
}
button.primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.as-of {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-left: auto;
}
.block {
  background: var(--surface);
  border: 1px solid var(--border-light);
  border-radius: 10px;
  padding: 18px 20px;
  margin: 16px 0;
}
.block-head {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 14px;
}
.block-title {
  font-size: 16px;
  font-weight: 700;
  margin: 0;
}
.block-sub {
  font-size: 13px;
  color: var(--text-tertiary);
}
.cards {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}
.chart-block {
  margin-top: 16px;
}
.chart-title {
  font-size: 14px;
  font-weight: 600;
  margin: 0 0 8px;
  color: var(--text-secondary);
}
.gap-notice {
  margin: 16px 0;
  padding: 14px 18px;
  border: 1px dashed var(--border-light);
  border-radius: 10px;
  background: var(--surface);
}
.gap-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.gap-notice ul {
  margin: 0;
  padding-left: 20px;
  font-size: 12px;
  color: var(--text-tertiary);
}
.gap-notice li {
  margin: 2px 0;
}
</style>
