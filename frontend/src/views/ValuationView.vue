<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SignalCard from '../components/SignalCard.vue'
import ResonanceSummary from '../components/ResonanceSummary.vue'
import EquityBondChart from '../components/EquityBondChart.vue'
import MeanAnchorChart from '../components/MeanAnchorChart.vue'
import CommodityChart from '../components/CommodityChart.vue'
import MacroChart from '../components/MacroChart.vue'
import MarginChart from '../components/MarginChart.vue'
import EtfShareChart from '../components/EtfShareChart.vue'
import NorthboundChart from '../components/NorthboundChart.vue'
import ValuationChannelChart from '../components/ValuationChannelChart.vue'
import {
  getResonance,
  getValuationIndices,
  type IndexItem,
  type Light,
  type ResonanceData,
  type SingleValuationData,
} from '../api'

// 控件
const indices = ref<IndexItem[]>([])
const symbol = ref('512890')
const lookback = ref('3y')
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

// 各层图表展开状态（默认全展开）
const expanded = ref<Record<string, boolean>>({
  base: false,
  layer1: false,
  layer2: false,
  layer3: false,
})
const lightColorMap: Record<string, string> = {
  green: '#3ba272',
  yellow: '#faad14',
  red: '#ee6666',
  grey: '#909399',
}

function toggle(key: string) {
  expanded.value[key] = !expanded.value[key]
  // 展开时触发图表 resize（容器从 display:none 恢复后 echarts 需要重算尺寸）
  if (expanded.value[key]) {
    nextTick(() => window.dispatchEvent(new Event('resize')))
  }
}

// ---- 指标卡片点击 → query 参数 → 展开对应层 + 滚动到图表 ----
const route = useRoute()
const router = useRouter()

// key → (slug, 所属层, 对应图表 ref id)
const METRIC_DETAIL: Record<string, { slug: string; layer: string; chartId: string }> = {
  // 基础层
  equity_bond: { slug: 'erp', layer: 'base', chartId: 'chart-equity-bond' },
  pe: { slug: 'pe', layer: 'base', chartId: 'chart-pe-channel' },
  ma120: { slug: 'ma120', layer: 'base', chartId: 'chart-pe-channel' },
  // 第一层（宏观）
  pmi: { slug: 'pmi', layer: 'layer1', chartId: 'chart-macro' },
  m1m2_gap: { slug: 'm1m2', layer: 'layer1', chartId: 'chart-macro' },
  sf_yoy: { slug: 'sf', layer: 'layer1', chartId: 'chart-macro' },
  ppi_yoy: { slug: 'ppi', layer: 'layer1', chartId: 'chart-macro' },
  // 第二层（高频行业）
  commodity_JM0: { slug: 'jm0', layer: 'layer2', chartId: 'chart-commodity' },
  commodity_CU0: { slug: 'cu0', layer: 'layer2', chartId: 'chart-commodity' },
  commodity_RB0: { slug: 'rb0', layer: 'layer2', chartId: 'chart-commodity' },
  commodity_BDI: { slug: 'bdi', layer: 'layer2', chartId: 'chart-commodity' },
  // 第三层（市场情绪）
  margin: { slug: 'margin', layer: 'layer3', chartId: 'chart-margin' },
  rqye: { slug: 'rqye', layer: 'layer3', chartId: 'chart-margin' },
  etf_share: { slug: 'etf-share', layer: 'layer3', chartId: 'chart-etf-share' },
  northbound: { slug: 'northbound', layer: 'layer3', chartId: 'chart-northbound' },
}

function goDetail(key: string) {
  const detail = METRIC_DETAIL[key]
  if (!detail) return
  router.push({ path: '/valuation', query: { metric: detail.slug } })
  expandAndScroll(detail.layer, detail.chartId)
}

function expandAndScroll(layer: string, chartId: string) {
  expanded.value[layer] = true
  nextTick(() => {
    window.dispatchEvent(new Event('resize'))
    setTimeout(() => {
      document.getElementById(chartId)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 200)
  })
}

// 基础层指标排序：MA120 → 回撤 → PE → PB → 股息率 → 股债比价
const BASE_ORDER = ['ma120', 'drawdown', 'pe', 'pb', 'dividend', 'equity_bond']
const baseMetrics = computed(() => {
  if (!data.value) return []
  return [...data.value.target.metrics].sort(
    (a, b) => (BASE_ORDER.indexOf(a.key) ?? 99) - (BASE_ORDER.indexOf(b.key) ?? 99),
  )
})

// 第二层（高频行业）：全收益偏离 + 股债比价 + 大宗商品
const layer2Metrics = computed(() => {
  if (!data.value) return []
  const keep = new Set(['equity_bond', 'commodity_JM0', 'commodity_CU0', 'commodity_RB0', 'commodity_BDI'])
  return data.value.market.metrics.filter((m) => keep.has(m.key) || m.key.startsWith('anchor_'))
})

// 第三层（市场情绪）：从 macro 取北向/融资/融券，从 market 取创业板/基金发行
const layer3Metrics = computed(() => {
  if (!data.value) return []
  const fromMacro = data.value.macro.metrics.filter((m) =>
    ['northbound', 'margin', 'rqye', 'etf_share'].includes(m.key),
  )
  const fromMarket = data.value.market.metrics.filter((m) =>
    ['style_ratio', 'fund_issue'].includes(m.key),
  )
  return [...fromMacro, ...fromMarket]
})

// 基础层：从 market 取全收益偏离（补到 target metrics 后面）
const baseAnchorMetric = computed(() => {
  if (!data.value) return null
  return data.value.market.metrics.find((m) => m.key.startsWith('anchor_')) ?? null
})

// ---- 前端复刻 layer_summary / resonance（按新四层重算）----
function layerSummary(lights: Light[]): Light {
  const voting = lights.filter((l) => l !== 'grey')
  if (!voting.length) return 'grey'
  const green = voting.filter((l) => l === 'green').length
  const red = voting.filter((l) => l === 'red').length
  const half = voting.length / 2
  if (green > half) return 'green'
  if (red > half) return 'red'
  return 'yellow'
}

function resonance4(l1: Light, l2: Light, l3: Light, l4: Light): { status: string; advice: string } {
  const real = [l1, l2, l3, l4].filter((l) => l !== 'grey')
  if (real.length && real.every((l) => l === 'green'))
    return { status: '🟢🟢🟢🟢 历史底部区域', advice: '重点关注，分批建仓区' }
  if (real.length && real.every((l) => l === 'red'))
    return { status: '🔴🔴🔴🔴 历史顶部区域', advice: '警惕，考虑减仓' }
  return { status: '🟡 不确定', advice: '保持纪律，不做大动作' }
}

// 四层汇总灯
const baseLight = computed<Light>(() => {
  if (!data.value) return 'grey'
  return layerSummary(data.value.target.metrics.map((m) => m.light))
})

const layer1Light = computed<Light>(() => {
  if (!data.value) return 'grey'
  return layerSummary(
    data.value.macro.metrics
      .filter((m) => ['pmi', 'm1m2_gap', 'sf_yoy', 'ppi_yoy'].includes(m.key))
      .map((m) => m.light),
  )
})

const layer2Light = computed<Light>(() => {
  if (!data.value) return 'grey'
  return layerSummary(layer2Metrics.value.map((m) => m.light))
})

const layer3Light = computed<Light>(() => {
  if (!data.value) return 'grey'
  return layerSummary(layer3Metrics.value.map((m) => m.light))
})

const resonanceResult = computed(() => {
  if (!data.value) return { status: '—', advice: '—' }
  return resonance4(baseLight.value, layer1Light.value, layer2Light.value, layer3Light.value)
})

const summaryLayers = computed(() => [
  { light: baseLight.value, name: '基础 技术估值', desc: '' },
  { light: layer1Light.value, name: '第一层 宏观领先', desc: '' },
  { light: layer2Light.value, name: '第二层 高频行业', desc: '' },
  { light: layer3Light.value, name: '第三层 市场情绪', desc: '' },
])

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
  await load()
  // query 预载：?metric=erp → 展开基础层 + 滚动到股债比价图
  const metric = route.query.metric
  if (typeof metric === 'string') {
    const entry = Object.values(METRIC_DETAIL).find((d) => d.slug === metric)
    if (entry) {
      // 等数据渲染完再展开滚动
      setTimeout(() => expandAndScroll(entry.layer, entry.chartId), 500)
    }
  }
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
          <option value="512890">华泰柏瑞红利低波ETF（512890）</option>
          <option value="510880">华泰柏瑞上证红利ETF（510880）</option>
          <option value="513920">华泰柏瑞港股央企红利ETF（513920）</option>
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
      <!-- 共振汇总 -->
      <div class="block resonance-block">
        <div class="block-head resonance-head">
          <h2 class="block-title">信号共振汇总</h2>
          <div class="resonance-layers">
            <span
              v-for="(layer, i) in summaryLayers" :key="i"
              class="resonance-layer"
            >
              <span class="resonance-dot" :style="{ background: lightColorMap[layer.light] }"></span>
              {{ layer.name }}
            </span>
          </div>
          <span class="resonance-status">{{ resonanceResult.status }}</span>
          <span class="resonance-advice">{{ resonanceResult.advice }}</span>
        </div>
      </div>

      <!-- 基础：技术 + 估值 -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">基础：技术 + 估值</h2>
          <span class="block-sub">
            {{ data.target.name_cn }}（{{ data.target.symbol }}）
            <template v-if="data.target.symbol !== data.target.resolved_index">
              · 跟踪 {{ data.target.index_name }}（{{ data.target.resolved_index }}）指数
            </template>
          </span>
          <button class="collapse-btn" @click="toggle('base')">{{ expanded.base ? '收起 ▲' : '展开 ▼' }}</button>
        </div>
        <div v-if="data.target.warning" class="warn">{{ data.target.warning }}</div>
        <div class="cards">
          <SignalCard
            v-for="m in baseMetrics" :key="m.key" :item="m"
            :clickable="!!METRIC_DETAIL[m.key]"
            @click="goDetail(m.key)"
          />
        </div>
        <div v-show="expanded.base" v-if="peChannelData" id="chart-pe-channel" class="chart-block">
          <h3 class="chart-title">PE 历史通道</h3>
          <ValuationChannelChart :data="peChannelData" />
        </div>
        <div v-show="expanded.base" v-if="data.target.equity_bond_chart" id="chart-equity-bond" class="chart-block">
          <h3 class="chart-title">股债比价通道</h3>
          <EquityBondChart :data="data.target.equity_bond_chart" />
        </div>
      </div>

      <!-- 第一层：宏观领先指标（未来利润方向） -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">第一层：宏观领先指标</h2>
          <span class="block-sub">未来利润方向</span>
          <button class="collapse-btn" @click="toggle('layer1')">{{ expanded.layer1 ? '收起 ▲' : '展开 ▼' }}</button>
        </div>
        <div v-if="data.macro.warning" class="warn">{{ data.macro.warning }}</div>
        <div v-if="data.macro.metrics.length" class="cards">
          <SignalCard
            v-for="m in data.macro.metrics.filter((m) => ['pmi','m1m2_gap','sf_yoy','ppi_yoy'].includes(m.key))"
            :key="m.key" :item="m"
            :clickable="!!METRIC_DETAIL[m.key]"
            @click="goDetail(m.key)"
          />
        </div>
        <p v-else class="muted">配置 Tushare Token 后可查看宏观信号（PMI/M1M2/社融/PPI）。</p>
        <div v-show="expanded.layer1" v-if="data.macro.macro_chart" id="chart-macro" class="chart-block">
          <h3 class="chart-title">宏观四指标趋势</h3>
          <MacroChart :data="data.macro.macro_chart" />
        </div>
      </div>

      <!-- 第二层：高频行业数据（跟踪实时经营） -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">第二层：高频行业数据</h2>
          <span class="block-sub">跟踪实时经营</span>
          <button class="collapse-btn" @click="toggle('layer2')">{{ expanded.layer2 ? '收起 ▲' : '展开 ▼' }}</button>
        </div>
        <div v-if="data.market.warning" class="warn">{{ data.market.warning }}</div>
        <div class="cards">
          <SignalCard v-if="baseAnchorMetric" :key="baseAnchorMetric.key" :item="baseAnchorMetric" />
          <SignalCard
            v-for="m in layer2Metrics" :key="m.key" :item="m"
            :clickable="!!METRIC_DETAIL[m.key]"
            @click="goDetail(m.key)"
          />
        </div>
        <div v-show="expanded.layer2" v-if="data.market.mean_anchor_chart" class="chart-block">
          <h3 class="chart-title">沪深300全收益 vs 5年均线</h3>
          <MeanAnchorChart :data="data.market.mean_anchor_chart" />
        </div>
        <div v-show="expanded.layer2" v-if="data.market.equity_bond_chart" class="chart-block">
          <h3 class="chart-title">沪深300 股债比价通道</h3>
          <EquityBondChart :data="data.market.equity_bond_chart" />
        </div>
        <div v-show="expanded.layer2" v-if="data.market.commodity_chart" id="chart-commodity" class="chart-block">
          <h3 class="chart-title">大宗商品走势（焦煤/沪铜/螺纹钢/BDI）</h3>
          <CommodityChart :data="data.market.commodity_chart" />
        </div>
      </div>

      <!-- 第三层：市场情绪指标（资金在用什么投票） -->
      <div class="block">
        <div class="block-head">
          <h2 class="block-title">第三层：市场情绪指标</h2>
          <span class="block-sub">资金在用什么投票</span>
          <button class="collapse-btn" @click="toggle('layer3')">{{ expanded.layer3 ? '收起 ▲' : '展开 ▼' }}</button>
        </div>
        <div v-if="layer3Metrics.length" class="cards">
          <SignalCard
            v-for="m in layer3Metrics" :key="m.key" :item="m"
            :clickable="!!METRIC_DETAIL[m.key]"
            @click="goDetail(m.key)"
          />
        </div>
        <p v-else class="muted">配置 Tushare Token 后可查看资金/情绪信号。</p>
        <div v-show="expanded.layer3" v-if="data.macro.margin_chart" id="chart-margin" class="chart-block">
          <h3 class="chart-title">融资余额 vs 沪深300</h3>
          <MarginChart :data="data.macro.margin_chart" />
        </div>
        <div v-show="expanded.layer3" v-if="data.macro.etf_share_chart" id="chart-etf-share" class="chart-block">
          <h3 class="chart-title">ETF 份额变动</h3>
          <EtfShareChart :data="data.macro.etf_share_chart" />
        </div>
        <div v-show="expanded.layer3" v-if="data.macro.northbound_chart" id="chart-northbound" class="chart-block">
          <h3 class="chart-title">北向资金净流入</h3>
          <NorthboundChart :data="data.macro.northbound_chart" />
        </div>
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
.collapse-btn {
  margin-left: auto;
  padding: 2px 10px;
  border: 1px solid var(--border-light);
  border-radius: 4px;
  background: var(--surface);
  color: var(--text-tertiary);
  font-size: 12px;
  cursor: pointer;
  white-space: nowrap;
}
.collapse-btn:hover {
  color: var(--text-primary);
  border-color: var(--text-tertiary);
}
.resonance-head {
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 0;
}
.resonance-block {
  padding: 18px 18px;
}
.resonance-layers {
  display: flex;
  gap: 14px;
  align-items: baseline;
  margin-left: 16px;
}
.resonance-layer {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.resonance-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}
.resonance-status {
  font-size: 16px;
  font-weight: 700;
  margin-left: auto;
}
.resonance-advice {
  font-size: 12px;
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
