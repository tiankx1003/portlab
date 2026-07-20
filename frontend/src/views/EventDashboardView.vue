<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import EventChainGraph from '../components/EventChainGraph.vue'
import DateInput from '../components/DateInput.vue'
import EventImpactChart from '../components/EventImpactChart.vue'
import CorrelationHeatmap from '../components/CorrelationHeatmap.vue'
import {
  createEvent,
  getEvent,
  getEventImpact,
  getLlmConfig,
  getTheme,
  listConceptStocks,
  listThemes,
  smartMatch,
  updateEventStocks,
  updateLlmConfig,
  type ChainRole,
  type EventBrief,
  type EventImpactData,
  type EventStockInput,
  type LlmConfigStatus,
  type MatchedStock,
  type ThemeBrief,
} from '../api'

// ---- LLM 配置 ----
const llmStatus = ref<LlmConfigStatus | null>(null)
const showLlmPanel = ref(false)
const llmForm = ref({ api_base: '', api_key: '', model: '', enabled: false })
const llmSaving = ref(false)
const llmTestMsg = ref('')
const llmTestLoading = ref(false)

async function loadLlm() {
  const r = await getLlmConfig()
  if (r.code === 0) {
    llmStatus.value = r.data
    llmForm.value.api_base = r.data.api_base
    llmForm.value.model = r.data.model
    llmForm.value.api_key = '' // 不回填明文，留空=不改
    llmForm.value.enabled = r.data.enabled
  }
}
function openLlmPanel() {
  llmTestMsg.value = ''
  loadLlm()
  showLlmPanel.value = true
}
function llmConfigured(): boolean {
  return !!(llmForm.value.api_base && llmForm.value.model && (llmForm.value.api_key || llmStatus.value?.api_key_masked))
}
async function saveLlm(test = false) {
  if (llmForm.value.enabled && !llmConfigured()) {
    llmTestMsg.value = '启用前请填写 api_base / api_key / model 三项'
    return
  }
  llmSaving.value = true
  llmTestMsg.value = ''
  try {
    const payload: Record<string, unknown> = {
      api_base: llmForm.value.api_base,
      model: llmForm.value.model,
      enabled: llmForm.value.enabled,
    }
    if (llmForm.value.api_key) payload.api_key = llmForm.value.api_key // 留空=不改
    const r = await updateLlmConfig({ ...payload, test })
    if (r.code !== 0) {
      llmTestMsg.value = r.message
      return
    }
    llmStatus.value = r.data
    if (test) {
      llmTestMsg.value = r.data.test ? `连接失败：${r.data.test}` : '✓ 连接成功'
    } else {
      llmTestMsg.value = '已保存'
      if (!llmForm.value.api_key) {
        // 保留掩码显示
        llmForm.value.api_key = ''
      }
      if (!test) setTimeout(() => (showLlmPanel.value = false), 500)
    }
  } finally {
    llmSaving.value = false
  }
}

// ---- 事件输入 + 智能匹配 ----
const evName = ref('')
const evDate = ref('')
const evDesc = ref('')
const matching = ref(false)
const matched = ref<MatchedStock[]>([])
const matchedSel = ref<Set<string>>(new Set())
const matchMsg = ref('')

async function runSmartMatch() {
  if (!evName.value.trim()) {
    matchMsg.value = '请先填写事件名'
    return
  }
  if (!llmStatus.value?.enabled) {
    matchMsg.value = '未配置 LLM，点击右上角 ⚙ 设置'
    return
  }
  matching.value = true
  matchMsg.value = ''
  matched.value = []
  matchedSel.value = new Set()
  try {
    const r = await smartMatch({ event_name: evName.value, description: evDesc.value })
    if (r.code !== 0) {
      matchMsg.value = r.message
      return
    }
    matched.value = r.data
    matchedSel.value = new Set(r.data.filter((m) => m.relevance !== 'none').map((m) => m.symbol))
    matchMsg.value = r.data.length ? `LLM 返回 ${r.data.length} 只相关标的，勾选后「加入标的池」` : 'LLM 未找到相关标的'
  } finally {
    matching.value = false
  }
}

// ---- 主题 / 概念补全 ----
const themes = ref<ThemeBrief[]>([])
const selThemeId = ref<number | null>(null)
const conceptInput = ref('')
const conceptLoading = ref(false)
const conceptResults = ref<{ symbol: string; name: string }[]>([])
const conceptSel = ref<Set<string>>(new Set())
const conceptMsg = ref('')

async function loadThemes() {
  const r = await listThemes()
  if (r.code === 0) themes.value = r.data
}
async function loadThemeToPool() {
  if (selThemeId.value == null) return
  const r = await getTheme(selThemeId.value)
  if (r.code !== 0) return
  for (const s of r.data.stocks) {
    addPool(s.symbol, s.chain_role)
  }
}
async function fetchConcept() {
  if (!conceptInput.value.trim()) return
  conceptLoading.value = true
  conceptMsg.value = ''
  conceptResults.value = []
  conceptSel.value = new Set()
  try {
    const r = await listConceptStocks(conceptInput.value)
    if (r.code !== 0) {
      conceptMsg.value = r.message
      return
    }
    conceptResults.value = r.data
    conceptMsg.value = r.data.length ? `概念「${conceptInput.value}」召回 ${r.data.length} 只，勾选后加入池` : '该概念无成分股'
  } finally {
    conceptLoading.value = false
  }
}
function addSelectedConceptToPool() {
  for (const s of conceptResults.value) {
    if (conceptSel.value.has(s.symbol)) addPool(s.symbol, 'midstream')
  }
}

// ---- 标的池 ----
const pool = ref<{ symbol: string; chain_role: ChainRole }[]>([])
const newSymbol = ref('')
const newRole = ref<ChainRole>('midstream')
const poolMsg = ref('')

function addPool(symbol: string, role: ChainRole) {
  const sym = symbol.trim()
  if (!sym) return
  if (pool.value.some((p) => p.symbol === sym)) {
    // 已存在则只更新角色
    const t = pool.value.find((p) => p.symbol === sym)
    if (t) t.chain_role = role
    return
  }
  pool.value.push({ symbol: sym, chain_role: role })
}
function addManual() {
  if (!newSymbol.value.trim()) return
  addPool(newSymbol.value, newRole.value)
  newSymbol.value = ''
}
function removePool(sym: string) {
  pool.value = pool.value.filter((p) => p.symbol !== sym)
}
function addMatchedSelected() {
  for (const m of matched.value) {
    if (matchedSel.value.has(m.symbol)) addPool(m.symbol, m.chain_role)
  }
}

// ---- 事件 CRUD + 影响查询 ----
const currentEvent = ref<EventBrief | null>(null)
const before = ref(20)
const after = ref(20)
const impact = ref<EventImpactData | null>(null)
const impactLoading = ref(false)
const impactMsg = ref('')
const selectedSymbol = ref<string | null>(null)
const ROLE_LABEL: Record<ChainRole, string> = { upstream: '上游', midstream: '中游', downstream: '下游' }
const REL_LABEL: Record<string, string> = { high: '高', medium: '中', low: '低', none: '无关' }
const REL_COLOR: Record<string, string> = { high: '#ee6666', medium: '#fa8c16', low: '#8a8f99', none: '#8a8f99' }

async function createEv() {
  if (!evName.value.trim() || !evDate.value) {
    poolMsg.value = '请填写事件名与日期'
    return
  }
  poolMsg.value = ''
  const stocks: EventStockInput[] = pool.value.map((p) => ({ symbol: p.symbol, chain_role: p.chain_role }))
  const r = await createEvent({
    name: evName.value,
    event_date: evDate.value,
    description: evDesc.value,
    stocks,
  })
  if (r.code !== 0) {
    poolMsg.value = r.message
    return
  }
  currentEvent.value = r.data
  poolMsg.value = `事件已创建（#${r.data.id}），可调整标的池或直接查询冲击`
  await loadImpact()
}
async function savePool() {
  if (!currentEvent.value) return
  const stocks = pool.value.map((p) => ({ symbol: p.symbol, chain_role: p.chain_role }))
  const r = await updateEventStocks(currentEvent.value.id, stocks)
  if (r.code !== 0) {
    poolMsg.value = r.message
    return
  }
  currentEvent.value = r.data
  poolMsg.value = '标的池已保存'
}
async function loadImpact() {
  if (!currentEvent.value) return
  impactLoading.value = true
  impactMsg.value = ''
  try {
    const r = await getEventImpact(currentEvent.value.id, { before: before.value, after: after.value })
    if (r.code !== 0) {
      impactMsg.value = r.message
      impact.value = null
      return
    }
    impact.value = r.data
    if (r.data.missing.length) impactMsg.value = `行情缺失：${r.data.missing.join(', ')}（其余标的已展示）`
  } finally {
    impactLoading.value = false
  }
}

const rankingSorted = computed(() => impact.value?.ranking ?? [])

onMounted(() => {
  loadLlm()
  loadThemes()
  evDate.value = new Date().toISOString().slice(0, 10)
})
</script>

<template>
  <section>
    <div class="page-head">
      <div>
        <h1>事件冲击产业链看板</h1>
        <p class="muted">某事件发生后，相关产业链上的股票怎么动、沿什么路径传导。多标的 × 事件 × 关系网络视角。</p>
      </div>
      <button class="icon-btn" title="LLM 设置" @click="openLlmPanel">⚙ LLM 设置</button>
    </div>

    <!-- 事件输入 + 智能匹配 -->
    <div class="form-card">
      <label>事件名
        <input v-model="evName" placeholder="如：茉莉花产地受灾" />
      </label>
      <label>事件日期
        <DateInput v-model="evDate" />
      </label>
      <label class="wide">事件描述（供智能匹配，将发送至大模型）
        <input v-model="evDesc" placeholder="如：主产区霜冻减产，影响花茶原料与现制茶饮、香料提取" />
      </label>
      <button class="primary" :disabled="matching || !llmStatus?.enabled" @click="runSmartMatch">
        {{ matching ? '匹配中…' : '🔍 智能匹配' }}
      </button>
      <button class="primary" @click="createEv">新建事件</button>
    </div>
    <p v-if="!llmStatus?.enabled" class="hint-warn">⚠ 未配置 LLM，智能匹配不可用，点击右上角「⚙ LLM 设置」开启。</p>
    <p v-else class="hint">LLM 已启用（{{ llmStatus.model }}）· 事件描述将发送至配置的大模型服务。</p>
    <p v-if="matchMsg" class="hint">{{ matchMsg }}</p>

    <!-- 智能匹配结果 -->
    <div v-if="matched.length" class="card">
      <div class="card-title">LLM 匹配结果（勾选后加入标的池）</div>
      <table class="mini">
        <thead><tr><th></th><th>代码</th><th>名称</th><th>环节</th><th>相关度</th><th>权重</th></tr></thead>
        <tbody>
          <tr v-for="m in matched" :key="m.symbol">
            <td><input type="checkbox" v-model="matchedSel" :value="m.symbol" /></td>
            <td>{{ m.symbol }}</td>
            <td>{{ m.name }}</td>
            <td><span class="chip" :class="m.chain_role">{{ ROLE_LABEL[m.chain_role] }}</span></td>
            <td><span :style="{ color: REL_COLOR[m.relevance], fontWeight: 600 }">{{ REL_LABEL[m.relevance] }}</span></td>
            <td>{{ m.weight.toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
      <button class="ghost" @click="addMatchedSelected">加入标的池</button>
    </div>

    <!-- 主题 / 概念补全 -->
    <div class="card">
      <div class="card-title">标的池管理</div>
      <div class="row">
        <label>选主题载入
          <select v-model="selThemeId" @change="loadThemeToPool">
            <option :value="null">— 选择主题 —</option>
            <option v-for="t in themes" :key="t.id" :value="t.id">{{ t.name }}（{{ t.stock_count }}）</option>
          </select>
        </label>
        <label>概念板块补全
          <div class="inline">
            <input v-model="conceptInput" placeholder="如：新茶饮 / 香精香料" />
            <button class="ghost" :disabled="conceptLoading" @click="fetchConcept">{{ conceptLoading ? '…' : '拉取' }}</button>
          </div>
        </label>
      </div>
      <p v-if="conceptMsg" class="hint">{{ conceptMsg }}</p>
      <div v-if="conceptResults.length" class="concept-list">
        <label v-for="c in conceptResults" :key="c.symbol" class="concept-item">
          <input type="checkbox" v-model="conceptSel" :value="c.symbol" />
          <span>{{ c.symbol }} {{ c.name }}</span>
        </label>
        <button class="ghost" @click="addSelectedConceptToPool">勾选项加入池</button>
      </div>

      <table class="pool">
        <thead><tr><th>代码</th><th>名称</th><th>产业链角色</th><th></th></tr></thead>
        <tbody>
          <tr v-for="p in pool" :key="p.symbol">
            <td>{{ p.symbol }}</td>
            <td>{{ impact?.symbols_info.find(s => s.symbol === p.symbol)?.name || '' }}</td>
            <td>
              <select v-model="p.chain_role">
                <option value="upstream">上游</option>
                <option value="midstream">中游</option>
                <option value="downstream">下游</option>
              </select>
            </td>
            <td><button class="link" @click="removePool(p.symbol)">删除</button></td>
          </tr>
        </tbody>
      </table>
      <div class="row">
        <input v-model="newSymbol" placeholder="手动添加代码（如 600598）" @keyup.enter="addManual" />
        <select v-model="newRole">
          <option value="upstream">上游</option>
          <option value="midstream">中游</option>
          <option value="downstream">下游</option>
        </select>
        <button class="ghost" @click="addManual">添加</button>
        <button v-if="currentEvent" class="primary" @click="savePool">保存标的池</button>
      </div>
      <p v-if="poolMsg" class="hint">{{ poolMsg }}</p>
    </div>

    <!-- 窗口控制 + 查询 -->
    <div v-if="currentEvent" class="form-card">
      <label>事件前 N 天
        <input v-model.number="before" type="number" min="0" max="120" />
      </label>
      <label>事件后 M 天
        <input v-model.number="after" type="number" min="0" max="120" />
      </label>
      <button class="primary" :disabled="impactLoading" @click="loadImpact">
        {{ impactLoading ? '查询中…（补拉行情）' : '查询冲击' }}
      </button>
      <span class="muted">当前事件：{{ currentEvent.name }}（{{ currentEvent.event_date }}）</span>
    </div>

    <p v-if="impactMsg" class="hint">{{ impactMsg }}</p>

    <!-- 三视图 -->
    <template v-if="impact">
      <div class="card">
        <div class="card-title">① 产业链关系图（上游 → 中游 → 下游传导）</div>
        <EventChainGraph :data="impact" :selected="selectedSymbol" @select="selectedSymbol = $event" />
        <p class="muted">节点颜色：红涨绿跌（窗口累计）；大小：波动幅度。点节点可与下方图表联动。</p>
      </div>

      <div class="card">
        <div class="card-title">② 事件窗口波动对比（事件日=0 基准）</div>
        <EventImpactChart :data="impact" />
      </div>

      <div class="card">
        <div class="card-title">② 涨跌排行榜（事件日 → 事件后 {{ after }} 天累计）</div>
        <table class="pool">
          <thead><tr><th>代码</th><th>名称</th><th>环节</th><th>累计涨跌</th></tr></thead>
          <tbody>
            <tr v-for="r in rankingSorted" :key="r.symbol" :class="{ hl: selectedSymbol === r.symbol }" @click="selectedSymbol = r.symbol">
              <td>{{ r.symbol }}</td>
              <td>{{ r.name }}</td>
              <td><span class="chip" :class="r.chain_role">{{ ROLE_LABEL[r.chain_role] }}</span></td>
              <td><span :style="{ color: r.change_pct >= 0 ? '#ee6666' : '#3ba272', fontWeight: 600 }">{{ r.change_pct >= 0 ? '+' : '' }}{{ r.change_pct.toFixed(2) }}%</span></td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="card-title">③ 传导相关性热力图（标的 × 标的）</div>
        <CorrelationHeatmap v-if="impact.correlation_symbols.length >= 2" :data="impact" />
        <p v-else class="hint">有效标的不足 2 只，无法计算相关性矩阵。</p>
        <p class="muted">蓝=负相关 / 红=正相关；对角线=1。用于发现「伪概念股」（板块内低相关）与隐藏传导链（跨环节高相关）。</p>
      </div>
    </template>
    <p v-else-if="!impactLoading && currentEvent" class="hint">点击「查询冲击」生成三视图。</p>

    <!-- LLM 设置面板 -->
    <Teleport to="body">
      <div v-if="showLlmPanel" class="modal-mask" @click.self="showLlmPanel = false">
        <div class="modal">
          <div class="modal-head">
            <b>LLM 设置（智能匹配）</b>
            <button class="link" @click="showLlmPanel = false">✕</button>
          </div>
          <div class="modal-body">
            <label>API Base
              <input v-model="llmForm.api_base" placeholder="https://api.deepseek.com 或 https://api.openai.com/v1" />
            </label>
            <label>API Key
              <input v-model="llmForm.api_key" type="password" :placeholder="llmStatus?.api_key_masked ? `已配置 ${llmStatus.api_key_masked}（留空=不改）` : 'sk-...'" />
            </label>
            <label>模型名
              <input v-model="llmForm.model" placeholder="deepseek-chat / gpt-4o-mini" />
            </label>
            <label class="toggle-row">
              <input type="checkbox" v-model="llmForm.enabled" :disabled="llmForm.enabled && false" />
              <span>启用智能匹配</span>
              <span v-if="llmForm.enabled && !llmConfigured()" class="hint-warn">三项未填齐</span>
            </label>
            <p v-if="llmTestMsg" class="hint">{{ llmTestMsg }}</p>
            <p class="muted small">配置永久保存于本服务后端，重启后依然有效。⚠ 事件描述将发送至配置的大模型服务，请勿输入敏感信息。</p>
          </div>
          <div class="modal-foot">
            <button class="ghost" :disabled="llmTestLoading" @click="saveLlm(true)">{{ llmTestLoading ? '…' : '测试连接' }}</button>
            <button class="primary" :disabled="llmSaving" @click="saveLlm(false)">{{ llmSaving ? '保存中…' : '保存' }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.page-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
.muted { color: var(--text-tertiary); font-size: 13px; }
.small { font-size: 12px; }
.hint { color: var(--text-secondary); font-size: 13px; margin: 6px 0; }
.hint-warn { color: var(--error-text); background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 6px; padding: 6px 10px; font-size: 13px; display: inline-block; }
.form-card {
  display: flex; gap: 12px; align-items: flex-end; flex-wrap: wrap;
  border: 1px solid var(--border-light); border-radius: 8px; padding: 14px 18px;
  background: var(--surface); margin: 12px 0;
}
label { display: flex; flex-direction: column; font-size: 13px; color: var(--text-secondary); gap: 4px; }
label.wide { min-width: 320px; flex: 1; }
input, select {
  padding: 8px 10px; border: 1px solid var(--input-border); border-radius: 6px;
  font-size: 14px; background: var(--input-bg); color: var(--text); min-width: 140px;
}
input[type='date'] { min-width: 150px; }
button.primary { background: var(--primary); color: #fff; border: none; border-radius: 6px; padding: 9px 18px; font-size: 14px; cursor: pointer; height: 38px; }
button.primary:disabled { background: var(--primary-disabled); cursor: not-allowed; }
button.ghost { background: transparent; color: var(--primary); border: 1px solid var(--primary); border-radius: 6px; padding: 8px 14px; font-size: 13px; cursor: pointer; }
button.ghost:disabled { opacity: 0.5; cursor: not-allowed; }
button.link { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 13px; }
button.icon-btn { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; cursor: pointer; color: var(--text-secondary); font-size: 13px; }
button.icon-btn:hover { background: var(--hover-bg); }
.card { border: 1px solid var(--border-light); border-radius: 8px; padding: 14px 18px; background: var(--surface); margin: 12px 0; }
.card-title { font-weight: 600; margin-bottom: 10px; color: var(--text); }
.row { display: flex; gap: 10px; align-items: flex-end; flex-wrap: wrap; margin-top: 8px; }
.inline { display: flex; gap: 6px; }
table.mini, table.pool { width: 100%; border-collapse: collapse; font-size: 13px; margin: 8px 0; }
table.mini th, table.mini td, table.pool th, table.pool td { padding: 6px 8px; border-bottom: 1px solid var(--border-light); text-align: left; }
table.pool tbody tr { cursor: pointer; }
table.pool tbody tr.hl { background: var(--hover-bg); }
.chip { font-size: 11px; padding: 2px 8px; border-radius: 10px; color: #fff; }
.chip.upstream { background: #5470c6; }
.chip.midstream { background: #fac858; color: #333; }
.chip.downstream { background: #ee6666; }
.concept-list { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; align-items: center; }
.concept-item { display: flex; align-items: center; gap: 4px; font-size: 12px; background: var(--hover-bg); padding: 4px 8px; border-radius: 6px; }
.toggle-row { flex-direction: row; align-items: center; gap: 8px; }
/* modal */
.modal-mask { position: fixed; inset: 0; background: rgba(0,0,0,0.4); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal { background: var(--surface); border-radius: 10px; width: 460px; max-width: 92vw; box-shadow: 0 8px 32px rgba(0,0,0,0.2); }
.modal-head { display: flex; justify-content: space-between; align-items: center; padding: 14px 18px; border-bottom: 1px solid var(--border-light); }
.modal-body { padding: 16px 18px; display: flex; flex-direction: column; gap: 12px; }
.modal-body label { gap: 6px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 10px; padding: 12px 18px; border-top: 1px solid var(--border-light); }
</style>
