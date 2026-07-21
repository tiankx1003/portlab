<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  fetchMarketData,
  getHealth,
  getMarketOverview,
  getRoadmap,
  listRecentBacktests,
  listReleaseNotes,
  type ApiResponse,
  type MarketOverview,
  type RecentBacktestItem,
  type ReleaseNoteItem,
  type ReleaseNoteType,
  type Roadmap,
} from '../api'

const router = useRouter()

// ---- Hero 健康状态 ----
const health = ref<ApiResponse<{ status: string }> | null>(null)
const healthOk = computed(() => health.value?.code === 0 && health.value?.data?.status === 'ok')

// ---- 最近回测 ----
const recent = ref<RecentBacktestItem[]>([])

// ---- 市场概览 ----
const market = ref<MarketOverview | null>(null)
const refreshing = ref(false)
const marketErr = ref('')
// 第 4 格：用户手动输入的代码（持久化到 localStorage）
const CUSTOM_KEY = 'home.market.custom'
const customSymbol = ref(localStorage.getItem(CUSTOM_KEY) || '')
const customInput = ref(customSymbol.value)
const customItem = computed(
  () => market.value?.items.find((i) => i.symbol === customSymbol.value) ?? null,
)
const presetItems = computed(() =>
  (market.value?.items ?? []).filter((i) => i.symbol !== customSymbol.value),
)
const presetMissing = computed(() =>
  (market.value?.missing ?? []).filter((s) => s !== customSymbol.value),
)

// ---- 最近更新（release notes 前 3）----
const notes = ref<ReleaseNoteItem[]>([])

// ---- Roadmap ----
const roadmap = ref<Roadmap | null>(null)

const TYPE_LABEL: Record<string, string> = { dca: 'DCA', ma120: 'MA120', drawboard: '回撤', grid: 'GRID' }
const NOTE_TYPE: Record<ReleaseNoteType, { label: string; cls: string }> = {
  feature: { label: '新功能', cls: 't-feature' },
  bugfix: { label: '修复', cls: 't-bugfix' },
  improvement: { label: '优化', cls: 't-improvement' },
  notice: { label: '公告', cls: 't-notice' },
}

/** sparkline 折线路径（纯 SVG，100×28 视口）。 */
function sparkPath(values: number[]): string {
  if (!values || values.length < 2) return ''
  const w = 100
  const h = 28
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const step = w / (values.length - 1)
  return values
    .map(
      (v, i) =>
        `${i === 0 ? 'M' : 'L'}${(i * step).toFixed(1)},${(h - ((v - min) / range) * h).toFixed(1)}`,
    )
    .join(' ')
}

function rateClass(rate: number): string {
  if (rate > 0) return 'up'
  if (rate < 0) return 'down'
  return 'flat'
}

async function loadAll() {
  try {
    health.value = await getHealth()
  } catch {
    health.value = null
  }
  try {
    const r = await listRecentBacktests(5)
    if (r.code === 0) recent.value = r.data
  } catch {
    /* 忽略 */
  }
  await loadMarket()
  try {
    const r = await listReleaseNotes()
    if (r.code === 0) notes.value = r.data.slice(0, 5)
  } catch {
    /* 忽略 */
  }
  try {
    const r = await getRoadmap()
    if (r.code === 0) roadmap.value = r.data
  } catch {
    /* 忽略 */
  }
}

async function loadMarket() {
  marketErr.value = ''
  try {
    const r = await getMarketOverview(customSymbol.value || undefined)
    if (r.code === 0) market.value = r.data
  } catch (e) {
    marketErr.value = e instanceof Error ? e.message : String(e)
  }
}

function applyCustom() {
  const code = customInput.value.trim()
  customSymbol.value = code
  if (code) localStorage.setItem(CUSTOM_KEY, code)
  else localStorage.removeItem(CUSTOM_KEY)
  loadMarket()
}

async function refreshMarket() {
  if (refreshing.value || !market.value) return
  refreshing.value = true
  marketErr.value = ''
  try {
    // 串行刷新（避免数据源限频）；最近 35 天覆盖到今天
    const today = new Date()
    const end = today.toISOString().slice(0, 10)
    const start = new Date(today.getTime() - 35 * 86400000).toISOString().slice(0, 10)
    const symbols = [...market.value.items.map((i) => i.symbol), ...market.value.missing]
    for (const sym of symbols) {
      await fetchMarketData(sym, start, end)
    }
    await loadMarket()
  } catch (e) {
    marketErr.value = e instanceof Error ? e.message : String(e)
  } finally {
    refreshing.value = false
  }
}

function openBacktest(item: RecentBacktestItem) {
  const path =
    item.type === 'ma120' ? '/ma120'
    : item.type === 'drawboard' ? '/drawboard'
    : item.type === 'grid' ? '/grid'
    : '/backtest'
  router.push({ path, query: { task: item.task_id } })
}

function chipClass(type: string): string {
  if (type === 'ma120') return 'c-ma120'
  if (type === 'drawboard') return 'c-drawboard'
  if (type === 'grid') return 'c-grid'
  return 'c-dca'
}

function gotoTools(path: string) {
  router.push(path)
}

onMounted(loadAll)
</script>

<template>
  <div class="home">
    <!-- Hero -->
    <section class="hero">
      <div class="hero-text">
        <h1 class="hero-title">
          PortLab
          <span
            class="health-dot"
            :class="healthOk ? 'ok' : 'bad'"
            :title="healthOk ? '后端正常' : '后端连接失败'"
          ></span>
        </h1>
        <p class="hero-sub">个人投资分析工具箱 · 定投 / MA120 策略回测</p>
      </div>
    </section>

    <!-- 功能入口卡片 -->
    <section class="entry-cards">
      <RouterLink class="entry-card" to="/backtest">
        <div class="entry-icon">
          <svg class="entry-svg" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path
              d="M746.55 170.64h74.655c53.011 0 95.985 42.974 95.985 95.985v554.58c0 53.011-42.974 95.985-95.985 95.985h-618.57c-53.011 0-95.985-42.974-95.985-95.985v-554.58c0-53.011 42.974-95.985 95.985-95.985h74.655v-42.66h63.99v42.66h341.28v-42.66h63.99v42.66z m0 63.99v42.66h-63.99v-42.66H341.28v42.66h-63.99v-42.66h-74.655c-17.67 0-31.995 14.325-31.995 31.995v554.58c0 17.67 14.325 31.995 31.995 31.995h618.57c17.67 0 31.995-14.325 31.995-31.995v-554.58c0-17.67-14.325-31.995-31.995-31.995H746.55zM511.92 642.488l-63.99-63.99-73.361 73.36-45.248-45.247L447.93 488.002l63.99 63.99 61.402-61.402h-29.407V426.6h183.893L511.92 642.488z"
              fill="currentColor"
            />
          </svg>
        </div>
        <div class="entry-body">
          <div class="entry-name">定投回测</div>
          <div class="entry-desc">普通 / 智能定投，XIRR 年化与最大回撤</div>
        </div>
        <div class="entry-arrow">进入 →</div>
      </RouterLink>
      <RouterLink class="entry-card" to="/ma120">
        <div class="entry-icon">
          <svg class="entry-svg" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            <path
              d="M903.5136 469.12a94.72 94.72 0 0 1-72.7168-34.048l-60.4032 24.704V633.6a25.6 25.6 0 0 1-25.6 25.6h-12.8v128a25.6 25.6 0 0 1-51.2 0v-128h-12.8a25.6 25.6 0 0 1-25.6-25.6V512l-64 26.112v57.088a25.6 25.6 0 0 1-25.6 25.6h-12.8v153.6a25.6 25.6 0 0 1-51.2 0v-153.6h-12.8a25.6 25.6 0 0 1-25.6-25.6v-4.608l-64 25.984v93.824a25.6 25.6 0 0 1-25.6 25.6h-12.8v140.8a25.6 25.6 0 1 1-51.2 0v-140.8h-12.8a25.6 25.6 0 0 1-25.6-25.6v-39.68l-46.2464 21.12a94.5408 94.5408 0 1 1-19.0592-37.248l65.28-26.624V531.2a25.6 25.6 0 0 1 25.6-25.6h12.8v-140.8a25.6 25.6 0 1 1 51.2 0v140.8h12.8a25.6 25.6 0 0 1 25.6 25.6v44.416l64-26.112V416a25.6 25.6 0 0 1 25.6-25.6h12.8v-128a25.6 25.6 0 0 1 51.2 0v128h12.8a25.6 25.6 0 0 1 25.6 25.6v81.152l64-26.24V339.2a25.6 25.6 0 0 1 25.6-25.6h12.8v-166.4a25.6 25.6 0 0 1 51.2 0v166.4h12.8a25.6 25.6 0 0 1 25.6 25.6v77.568l41.3568-18.944a94.72 94.72 0 1 1 91.7888 71.296zM120.4224 658.56a56.832 56.832 0 1 0 56.8832 56.832 56.8832 56.8832 0 0 0-56.896-56.832z m783.0912-340.992a56.832 56.832 0 1 0 56.8832 56.832 56.7936 56.7936 0 0 0-56.8832-56.832z"
              fill="currentColor"
            />
          </svg>
        </div>
        <div class="entry-body">
          <div class="entry-name">MA120 策略</div>
          <div class="entry-desc">红利 ETF 均线策略，金字塔分批买卖</div>
        </div>
        <div class="entry-arrow">进入 →</div>
      </RouterLink>
      <RouterLink class="entry-card" to="/drawboard">
        <div class="entry-icon">
          <svg class="entry-svg entry-line-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke="currentColor" stroke-width="20" stroke-linejoin="round" stroke-linecap="round">
            <path
              d="M119.552 65.706667a21.333333 21.333333 0 0 1 26.197333 7.808l1.834667 3.370666 131.669333 305.152 54.528-90.88a21.333333 21.333333 0 0 1 37.077334 0.768l1.450666 3.498667 140.074667 423.765333 97.706667-150.272a21.333333 21.333333 0 0 1 29.781333-6.101333l3.072 2.474667 58.538667 57.472 174.634666-448.128a21.333333 21.333333 0 0 1 23.893334-13.226667l3.754666 1.109333a21.333333 21.333333 0 0 1 13.184 23.893334l-1.066666 3.712-186.368 478.293333a21.333333 21.333333 0 0 1-31.914667 9.813333l-2.901333-2.346666-63.061334-61.866667-107.690666 165.674667a21.333333 21.333333 0 0 1-36.522667-1.28l-1.621333-3.669334L346.453333 352.938667l-51.968 86.741333a21.333333 21.333333 0 0 1-36.053333 0.938667l-1.834667-3.413334L108.373333 93.738667a21.333333 21.333333 0 0 1 11.093334-28.032z"
              fill="currentColor"
            />
            <path
              d="M128 64a21.333333 21.333333 0 0 1 20.992 17.493333L149.333333 85.333333v682.666667a64 64 0 0 0 57.856 63.701333L213.333333 832h682.666667a21.333333 21.333333 0 0 1 3.84 42.325333L896 874.666667H213.333333a106.666667 106.666667 0 0 1-106.453333-99.669334L106.666667 768V85.333333a21.333333 21.333333 0 0 1 21.333333-21.333333z"
              fill="currentColor"
            />
          </svg>
        </div>
        <div class="entry-body">
          <div class="entry-name">回撤看板</div>
          <div class="entry-desc">回撤阈值金字塔买入，复利再投</div>
        </div>
        <div class="entry-arrow">进入 →</div>
      </RouterLink>
      <RouterLink class="entry-card" to="/grid">
        <div class="entry-icon">
          <svg class="entry-svg entry-line-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" stroke="currentColor" stroke-width="20" stroke-linejoin="round" stroke-linecap="round">
            <path
              d="M897.194667 148.195556c5.404444 0 10.012444 4.551111 10.012444 10.012444v709.973333c0 5.404444-4.608 10.012444-10.012444 10.012445H126.862222a10.183111 10.183111 0 0 1-10.012444-10.012445V158.208c0-5.404444 4.608-10.012444 10.012444-10.012444H897.137778m0-50.005334H126.862222c-32.995556 0-60.017778 27.022222-60.017778 60.017778v709.973333c0 32.995556 27.022222 60.017778 60.017778 60.017778H897.137778c32.995556 0 60.017778-27.022222 60.017778-60.017778V158.208c0-32.995556-27.022222-60.017778-60.017778-60.017778z"
              fill="currentColor"
            />
            <path
              d="M523.093333 247.466667a21.788444 21.788444 0 0 1 20.138667 12.8l1.479111 4.323555 0.568889 4.608-0.056889 13.368889 3.413333 0.796445c24.064 6.826667 44.145778 23.210667 55.978667 45.056l4.551111 9.728 3.470222 10.296888 0.568889 2.844445 141.539556 0.056889a21.617778 21.617778 0 0 1 7.452444 1.251555l3.413334 1.592889 4.551111 3.470222a21.845333 21.845333 0 0 1-9.671111 36.522667l-5.688889 0.853333h-141.653334l-0.568888 2.958223a92.444444 92.444444 0 0 1-44.373334 56.547555l-9.671111 4.664889-10.296889 3.584-3.015111 0.682667-0.113778 78.904889 209.749334 0.056889c2.56 0 5.12 0.512 7.395555 1.365333l3.470222 1.649778 4.551112 3.470222a21.788444 21.788444 0 0 1-0.113778 30.833778 21.674667 21.674667 0 0 1-9.728 5.688889l-5.688889 0.682666-209.635556-0.113778 0.170667 253.895112c0 5.688889-2.275556 10.979556-6.257778 14.961777l-4.551111 3.584-5.632 2.56-5.688889 0.739556a21.447111 21.447111 0 0 1-18.318222-10.808889l-2.503111-5.575111-0.739556-5.518222 0.113778-62.464-189.895111-0.056889 0.113778 62.691555c0 9.329778-3.925333 16.156444-10.695111 19.512889l-5.688889 1.820445-5.461334 0.512c-11.719111 0-19.456-6.087111-21.447111-16.327111l-0.512-5.518223v-62.691555l-84.195555 0.113778c-9.272889 0-16.099556-3.868444-19.456-10.695112l-1.820445-5.632-0.512-5.461333c0-11.719111 6.087111-19.456 16.327111-21.447111l5.518223-0.512h84.138666v-147.683556l-83.854222 0.113778a21.845333 21.845333 0 0 1-7.509333-1.251555l-3.470222-1.536-4.551112-3.470223a21.902222 21.902222 0 0 1-6.599111-15.587555 22.016 22.016 0 0 1 17.009778-21.276445l5.006222-0.568888 83.968-0.056889V394.922667l-83.968 0.113777a21.959111 21.959111 0 0 1-19.285333-11.434666l-2.104889-5.518222-0.625778-5.063112a21.845333 21.845333 0 0 1 16.384-21.048888l5.632-0.625778h83.968v-81.92c0-9.329778 3.925333-16.156444 10.695111-19.512889l5.688889-1.877333 5.461334-0.455112c11.719111 0 19.456 6.030222 21.447111 16.327112l0.512 5.461333-0.113778 81.92h120.945778l0.682666-3.242667c6.656-24.348444 22.983111-44.714667 44.999112-56.718222l9.784888-4.608 10.410667-3.527111 2.958222-0.625778v-13.198222c0-2.56 0.341333-5.12 1.194667-7.509333l1.592889-3.413334 3.413333-4.608a21.333333 21.333333 0 0 1 15.303111-6.371555z m-21.504 338.602666H311.921778v147.626667h189.781333l-0.113778-147.626667z m-189.667555-191.146666v147.456h189.667555v-78.506667l-3.413333-0.625778a92.444444 92.444444 0 0 1-56.718222-44.999111l-4.551111-9.784889-3.584-10.410666-0.682667-3.015112-120.718222-0.113777z m211.171555-71.68a41.358222 41.358222 0 0 0-10.922666 1.365333 48.924444 48.924444 0 0 0-37.546667 37.148444 47.104 47.104 0 0 0 0 22.641778 49.152 49.152 0 0 0 37.944889 37.205334c3.413333 0.853333 6.826667 1.308444 10.524444 1.251555a41.984 41.984 0 0 0 11.946667-1.592889 49.777778 49.777778 0 0 0 30.890667-22.755555l3.413333-6.940445 2.275556-7.054222a47.160889 47.160889 0 0 0 0-22.869333 49.664 49.664 0 0 0-36.977778-36.920889 41.244444 41.244444 0 0 0-11.548445-1.536z"
              fill="currentColor"
            />
          </svg>
        </div>
        <div class="entry-body">
          <div class="entry-name">网格交易</div>
          <div class="entry-desc">中枢间距双向触发，吃震荡波段</div>
        </div>
        <div class="entry-arrow">进入 →</div>
      </RouterLink>
    </section>

    <!-- 市场概览 -->
    <section class="block">
      <div class="block-head">
        <h2 class="block-title">市场概览</h2>
        <div class="block-meta">
          <span v-if="market?.as_of" class="muted">数据截至 {{ market.as_of }}</span>
          <button
            class="refresh-btn"
            :class="{ spinning: refreshing }"
            type="button"
            :disabled="refreshing || !market"
            :title="refreshing ? '刷新中…' : '刷新行情'"
            aria-label="刷新行情"
            @click="refreshMarket"
          >
            <svg class="refresh-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
              <path
                d="M512.020978 256.514211l0-95.771227-127.737266 127.695311 127.737266 127.780245 0-95.834672c105.369839 0 191.585433 86.214571 191.585433 191.605899 0 31.902594-9.556657 63.848167-22.325471 89.408309l47.864124 47.88459c22.367427-41.521672 38.310537-86.214571 38.310537-137.293923C767.454578 371.482663 652.528082 256.514211 512.020978 256.514211M512.020978 703.5752c-105.411795 0-191.585433-86.215594-191.585433-191.585433 0-31.924083 9.556657-63.868633 22.325471-89.428775l-47.864124-47.864124c-22.367427 41.521672-38.352493 86.194104-38.352493 137.292899 0 140.507104 114.968451 255.454066 255.475556 255.454066l0 95.813183 127.737266-127.7168-127.737266-127.780245L512.019954 703.5752z"
                fill="currentColor"
              />
            </svg>
          </button>
        </div>
      </div>
      <p v-if="marketErr" class="err">{{ marketErr }}</p>
      <div v-if="market" class="market-grid">
        <div v-for="it in presetItems" :key="it.symbol" class="market-card">
          <div class="market-head">
            <span class="market-name">{{ it.name }}</span>
            <span class="market-code">{{ it.symbol }}</span>
          </div>
          <div class="market-price">{{ it.latest_close.toFixed(3) }}</div>
          <div class="market-chg" :class="rateClass(it.change_pct ?? 0)">
            {{ it.change_pct != null ? (it.change_pct > 0 ? '+' : '') + it.change_pct.toFixed(2) + '%' : '—' }}
          </div>
          <svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
            <path :d="sparkPath(it.sparkline)" :class="rateClass(it.change_pct ?? 0)" fill="none" stroke-width="1.5" />
          </svg>
        </div>
        <div v-for="sym in presetMissing" :key="'m-' + sym" class="market-card market-missing">
          <div class="market-head">
            <span class="market-name muted">暂无行情</span>
            <span class="market-code">{{ sym }}</span>
          </div>
          <div class="market-hint">点「刷新行情」拉取</div>
        </div>
        <!-- 第 4 格：左上角名称、右上角代码（可编辑输入框） -->
        <div class="market-card market-custom">
          <div class="market-head">
            <span class="market-name">{{ customItem?.name || customSymbol || '自定义' }}</span>
            <input
              v-model="customInput"
              class="market-code-input"
              type="text"
              maxlength="10"
              placeholder="代码"
              title="输入代码后回车"
              @keyup.enter="applyCustom"
            />
          </div>
          <template v-if="customItem">
            <div class="market-price">{{ customItem.latest_close.toFixed(3) }}</div>
            <div class="market-chg" :class="rateClass(customItem.change_pct ?? 0)">
              {{ customItem.change_pct != null ? (customItem.change_pct > 0 ? '+' : '') + customItem.change_pct.toFixed(2) + '%' : '—' }}
            </div>
            <svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
              <path :d="sparkPath(customItem.sparkline)" :class="rateClass(customItem.change_pct ?? 0)" fill="none" stroke-width="1.5" />
            </svg>
          </template>
          <div v-else class="market-hint">
            {{ customSymbol ? '暂无行情，点「刷新行情」拉取' : '输入代码回车查看' }}
          </div>
        </div>
      </div>
    </section>

    <!-- 最近回测记录 -->
    <section class="block">
      <div class="block-head">
        <h2 class="block-title">最近回测记录</h2>
      </div>
      <div v-if="!recent.length" class="empty">
        还没有回测记录，去
        <a class="link" @click="gotoTools('/backtest')">试试定投回测</a>
      </div>
      <ul v-else class="recent-list">
        <li v-for="it in recent" :key="it.task_id" class="recent-row" @click="openBacktest(it)">
          <span class="chip" :class="chipClass(it.type)">
            {{ TYPE_LABEL[it.type] || it.type }}
          </span>
          <span class="recent-symbol">{{ it.symbol_name || it.symbol }}</span>
          <span class="recent-rate" :class="rateClass(it.return_rate)">
            {{ it.return_rate > 0 ? '+' : '' }}{{ it.return_rate.toFixed(2) }}%
          </span>
          <span class="recent-date muted">{{ it.created_text }}</span>
        </li>
      </ul>
    </section>

    <!-- 最近更新 + Roadmap（两栏）-->
    <section class="two-col">
      <div class="block col">
        <div class="block-head">
          <h2 class="block-title">最近更新</h2>
        </div>
        <ul v-if="notes.length" class="notes-list">
          <li v-for="n in notes" :key="n.id" class="note-row">
            <span class="chip" :class="NOTE_TYPE[n.type]?.cls || 't-notice'">
              {{ NOTE_TYPE[n.type]?.label || n.type }}
            </span>
            <span class="note-title">{{ n.title }}</span>
            <span class="note-date muted">{{ n.released_at }}</span>
          </li>
        </ul>
        <p v-else class="empty">暂无更新</p>
        <p class="muted note-tip">完整列表见右上角铃铛「更新日志」</p>
      </div>

      <div class="block col">
        <div class="block-head">
          <h2 class="block-title">Roadmap · 规划中</h2>
        </div>
        <ul v-if="roadmap?.items.length" class="roadmap-list">
          <li v-for="r in roadmap.items" :key="r.id" class="roadmap-row" :title="'查看 ' + r.doc_url">
            <span class="roadmap-id">{{ r.id }}</span>
            <div class="roadmap-body">
              <div class="roadmap-title">{{ r.title }}</div>
              <div class="roadmap-summary muted">{{ r.summary }}</div>
            </div>
          </li>
        </ul>
        <p v-else class="empty">暂无规划，敬请期待 🎉</p>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
.muted {
  color: var(--text-tertiary);
  font-size: 12px;
}
.err {
  color: var(--error-text);
  font-size: 13px;
}
.link {
  color: var(--primary);
  cursor: pointer;
  text-decoration: underline;
}

/* Hero */
.hero-title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  display: flex;
  align-items: center;
  gap: 10px;
}
.hero-sub {
  margin: 6px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
}
.health-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  display: inline-block;
}
.health-dot.ok {
  background: #00a870;
  box-shadow: 0 0 0 3px color-mix(in srgb, #00a870 25%, transparent);
}
.health-dot.bad {
  background: var(--text-tertiary);
}

/* 功能入口卡片 */
.entry-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.entry-card {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  text-decoration: none;
  color: var(--text);
  transition: box-shadow 0.2s, transform 0.2s, border-color 0.2s;
}
.entry-card:hover {
  box-shadow: 0 8px 24px var(--shadow);
  transform: translateY(-2px);
  border-color: var(--primary);
}
.entry-icon {
  font-size: 26px;
  display: flex;
  align-items: center;
}
.entry-svg {
  width: 30px;
  height: 30px;
  color: #ee6666;
}
/* 线条型图标（回撤/网格）：略缩 + 同色 stroke 加粗，与实心图标观感一致 */
.entry-line-icon {
  width: 27px;
  height: 27px;
}
.entry-body {
  flex: 1;
}
.entry-name {
  font-size: 16px;
  font-weight: 600;
}
.entry-desc {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}
.entry-arrow {
  font-size: 13px;
  color: var(--primary);
}

/* 通用 block */
.block {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px;
}
.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.block-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.block-meta {
  display: flex;
  align-items: center;
  gap: 12px;
}
.refresh-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
}
.refresh-btn:hover:not(:disabled) {
  color: var(--primary);
  background: var(--hover-bg);
}
.refresh-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.refresh-icon {
  width: 18px;
  height: 18px;
}
.refresh-btn.spinning .refresh-icon {
  animation: ds-spin 0.9s linear infinite;
}
@keyframes ds-spin {
  to {
    transform: rotate(360deg);
  }
}

/* 市场概览 */
.market-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}
.market-card {
  padding: 14px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--input-bg);
}
.market-missing {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.market-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  height: 22px;
  margin-bottom: 2px;
}
.market-code {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.market-code-input {
  flex-shrink: 0;
  width: 84px;
  height: 22px;
  box-sizing: border-box;
  padding: 0 6px;
  border: 1px solid var(--input-border);
  border-radius: 5px;
  background: var(--surface);
  color: var(--text-secondary);
  font-size: 12px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.market-code-input:focus {
  outline: none;
  border-color: var(--primary);
}
.market-name {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.market-price {
  font-size: 20px;
  font-weight: 700;
  margin-top: 4px;
}
.market-chg {
  font-size: 13px;
  font-weight: 600;
  margin-top: 2px;
}
.market-hint {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 6px;
}
.spark {
  width: 100%;
  height: 28px;
  margin-top: 8px;
  display: block;
}
.spark .up {
  stroke: #ee6666;
}
.spark .down {
  stroke: #3ba272;
}
.spark .flat {
  stroke: var(--text-tertiary);
}

/* 涨跌色（红涨绿跌） */
.up {
  color: #ee6666;
}
.down {
  color: #3ba272;
}
.flat {
  color: var(--text-tertiary);
}

/* 最近回测 */
.recent-list,
.notes-list,
.roadmap-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.recent-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-bottom: 1px solid var(--border-light);
  cursor: pointer;
  transition: background 0.15s;
}
.recent-row:last-child {
  border-bottom: none;
}
.recent-row:hover {
  background: var(--hover-bg);
}
.recent-symbol {
  flex: 1;
  font-size: 14px;
}
.recent-rate {
  font-size: 14px;
  font-weight: 600;
}
.recent-date {
  font-size: 12px;
}

/* chip */
.chip {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.6;
  min-width: 44px;
  text-align: center;
}
.c-dca {
  background: color-mix(in srgb, var(--primary) 16%, transparent);
  color: var(--primary);
}
.c-ma120 {
  background: color-mix(in srgb, #faad14 20%, transparent);
  color: #d48806;
}
.c-drawboard {
  background: color-mix(in srgb, #5470c6 20%, transparent);
  color: #3a5bbf;
}
.c-grid {
  background: color-mix(in srgb, #3ba272 20%, transparent);
  color: #2f8a5f;
}
.t-feature {
  background: color-mix(in srgb, #3ba272 18%, transparent);
  color: #2f8a5f;
}
.t-bugfix {
  background: color-mix(in srgb, #ee6666 18%, transparent);
  color: #d94c4c;
}
.t-improvement {
  background: color-mix(in srgb, var(--primary) 18%, transparent);
  color: var(--primary);
}
.t-notice {
  background: var(--hover-bg);
  color: var(--text-secondary);
}

/* 两栏 */
.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.note-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}
.note-row:last-child {
  border-bottom: none;
}
.note-title {
  flex: 1;
  font-size: 13px;
}
.note-date {
  font-size: 12px;
}
.note-tip {
  margin-top: 12px;
}

/* roadmap */
.roadmap-row {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
}
.roadmap-row:last-child {
  border-bottom: none;
}
.roadmap-id {
  flex-shrink: 0;
  width: 30px;
  height: 24px;
  border-radius: 6px;
  background: var(--hover-bg);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.roadmap-title {
  font-size: 13px;
  font-weight: 600;
}
.roadmap-summary {
  font-size: 12px;
  margin-top: 2px;
}

.empty {
  color: var(--text-tertiary);
  font-size: 13px;
  padding: 8px 0;
}

/* 响应式 */
@media (max-width: 1100px) {
  .entry-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
@media (max-width: 900px) {
  .market-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .two-col {
    grid-template-columns: 1fr;
  }
}
@media (max-width: 560px) {
  .entry-cards {
    grid-template-columns: 1fr;
  }
  .market-grid {
    grid-template-columns: 1fr;
  }
}
</style>
