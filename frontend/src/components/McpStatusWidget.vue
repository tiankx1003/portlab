<script setup lang="ts">
import { computed, ref } from 'vue'
import { getMcpStatus, type McpStatusData, type McpToolItem } from '../api'

const show = ref(false)
const status = ref<McpStatusData | null>(null)
const loading = ref(false)
const error = ref('')
const expanded = ref(false)
const copied = ref('') // 'url' | 'config' | ''

// 状态灯：运行中（绿）/ 未启动（灰）/ 后端不通（黄）
const lightColor = computed(() => {
  if (!status.value) return 'grey'
  if (!status.value.enabled) return 'grey'
  return status.value.backend_reachable ? 'green' : 'yellow'
})
const lightText = computed(() => {
  if (!status.value) return '检测中…'
  if (!status.value.enabled) return '未启动'
  return status.value.backend_reachable ? '运行中' : '后端未连通'
})

const GROUP_LABEL: Record<string, string> = {
  system: '系统 / 元信息',
  market: '市场 / 估值',
  backtest: '回测',
  drawboard: '回撤看板',
  event: '事件冲击',
  arena: '策略擂台',
}
// 按分组聚合 tool 列表（保持分组顺序）
const groupedTools = computed<{ group: string; label: string; items: McpToolItem[] }[]>(() => {
  const tools = status.value?.tools ?? []
  const order = ['system', 'market', 'backtest', 'drawboard', 'event', 'arena']
  const byGroup = new Map<string, McpToolItem[]>()
  for (const t of tools) {
    if (!byGroup.has(t.group)) byGroup.set(t.group, [])
    byGroup.get(t.group)!.push(t)
  }
  return order
    .filter((g) => byGroup.has(g))
    .map((g) => ({ group: g, label: GROUP_LABEL[g] ?? g, items: byGroup.get(g)! }))
})

const zcodeConfig = computed(() =>
  JSON.stringify({ mcpServers: { portlab: { url: status.value?.mcp_url ?? '' } } }, null, 2),
)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await getMcpStatus()
    if (r.code === 0) status.value = r.data
    else error.value = r.message
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function open() {
  show.value = true
  expanded.value = false
  load()
}
function close() {
  show.value = false
}

async function copy(text: string, tag: 'url' | 'config') {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
    } else {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.style.position = 'fixed'
      ta.style.opacity = '0'
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
    }
    copied.value = tag
    setTimeout(() => {
      copied.value = ''
    }, 2000)
  } catch {
    /* 忽略复制失败 */
  }
}

function formatTime(iso: string): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false })
  } catch {
    return iso
  }
}
</script>

<template>
  <button class="mcp-btn" type="button" title="MCP Server" aria-label="MCP Server 状态" @click="open">
    <svg
      class="mcp-icon"
      viewBox="0 0 1024 1024"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <g
        fill="currentColor"
        stroke="currentColor"
        stroke-width="56"
        stroke-linejoin="round"
        stroke-linecap="round"
      >
      <path
        d="M580.5056 135.8336c24.576 0 48.128 9.5744 65.7408 26.6752 35.584 34.6624 36.3008 91.648 1.6384 127.232l-1.536 1.536-264.7552 259.7888a29.99296 29.99296 0 0 0-0.512 42.3936l0.512 0.512a31.34464 31.34464 0 0 0 43.776 0l3.584-3.5328 261.2224-256.256c36.608-35.5328 94.8736-35.4816 131.3792 0.1024l1.8432 1.8432c35.584 34.6624 36.352 91.648 1.6384 127.232l-1.6384 1.6384-317.0816 310.8864c-27.6992 26.8288-28.3648 71.0656-1.536 98.7648l1.536 1.536 65.0752 63.7952c12.4416 12.032 32.3584 11.7248 44.3904-0.7168 2.56-2.6624 4.6592-5.7344 6.144-9.1136 4.8128-11.3664 2.1504-24.5248-6.7072-33.1264l-65.1264-63.8976c-3.9424-3.84-4.0448-10.1376-0.2048-14.08l0.2048-0.2048 317.0304-310.8864c59.3408-57.7536 60.5696-152.6784 2.816-212.0192-0.9216-0.9728-1.8432-1.8432-2.816-2.816l-1.8432-1.8432a156.52352 156.52352 0 0 0-131.4304-42.9568 149.7088 149.7088 0 0 0-43.8784-128.8704c-60.9792-59.2896-158.0544-59.2896-219.0336 0L120.576 463.2576a29.94688 29.94688 0 0 0-0.5632 42.3936l0.5632 0.5632a31.4368 31.4368 0 0 0 43.776 0l350.5152-343.7056a94.208 94.208 0 0 1 65.6896-26.6752z"
        fill="currentColor"
      />
      <path
        d="M609.1776 238.592c-1.5872 3.6864-3.84 7.0656-6.7584 9.8304L343.296 502.6816c-35.584 34.6624-36.3008 91.648-1.6384 127.232 0.5632 0.5632 1.0752 1.1264 1.6384 1.6384 36.5568 35.584 94.8224 35.584 131.3792 0l259.1744-254.2592c12.4416-12.1344 32.3584-11.8272 44.4928 0.6144 2.6112 2.6624 4.7104 5.7856 6.2464 9.216 4.8128 11.3664 2.0992 24.576-6.8096 33.1264l-259.2768 254.2592c-60.9792 59.3408-158.1056 59.3408-219.0848 0-59.2896-57.6512-60.672-152.4224-3.0208-211.7632 0.9728-1.024 1.9968-2.048 3.0208-3.0208l259.2256-254.2592a31.40096 31.40096 0 0 1 50.5856 9.8304c3.1232 7.424 3.1232 15.872 0 23.296h-0.0512z"
        fill="currentColor"
      />
      </g>
    </svg>
  </button>

  <Teleport to="body">
    <div v-if="show" class="mcp-overlay" @click.self="close">
      <div class="mcp-panel" role="dialog" aria-modal="true" aria-label="MCP Server 状态">
        <div class="mcp-header">
          <span class="mcp-title">MCP Server</span>
          <button class="mcp-close" type="button" aria-label="关闭" @click="close">✕</button>
        </div>

        <div class="mcp-body">
          <p v-if="loading && !status" class="mcp-muted">检测中…</p>
          <div v-else-if="error" class="mcp-muted">
            检测失败：{{ error }}
          </div>
          <template v-else-if="status">
            <!-- 状态灯 -->
            <div class="mcp-row">
              <span class="mcp-label">状态</span>
              <span class="mcp-status">
                <i class="mcp-dot" :class="`d-${lightColor}`"></i>{{ lightText }}
              </span>
            </div>

            <!-- 连接地址 + 复制 -->
            <div class="mcp-row">
              <span class="mcp-label">连接地址</span>
              <span class="mcp-url-wrap">
                <code class="mcp-url">{{ status.mcp_url }}</code>
                <button
                  class="mcp-copy-mini"
                  type="button"
                  title="复制地址"
                  @click="copy(status.mcp_url, 'url')"
                >
                  {{ copied === 'url' ? '✓' : '📋' }}
                </button>
              </span>
            </div>

            <!-- 后端连通 -->
            <div class="mcp-row">
              <span class="mcp-label">后端连通</span>
              <span>{{ status.backend_reachable ? '✓ 正常' : '✗ 不可达' }}</span>
            </div>

            <!-- 已暴露工具 -->
            <div class="mcp-row">
              <span class="mcp-label">已暴露工具</span>
              <span>{{ status.tool_count }} 个</span>
            </div>

            <button
              v-if="status.tool_count"
              class="mcp-expand"
              type="button"
              @click="expanded = !expanded"
            >
              {{ expanded ? '收起工具列表' : '展开工具列表' }}
              <span class="mcp-caret">{{ expanded ? '▲' : '▼' }}</span>
            </button>
            <div v-if="expanded && groupedTools.length" class="mcp-groups">
              <div v-for="g in groupedTools" :key="g.group" class="mcp-group">
                <div class="mcp-group-title">{{ g.label }}（{{ g.items.length }}）</div>
                <div v-for="t in g.items" :key="t.name" class="mcp-tool">
                  <code class="mcp-tool-name">{{ t.name }}</code>
                  <span class="mcp-tool-desc">{{ t.desc }}</span>
                </div>
              </div>
            </div>

            <!-- 最近检查 -->
            <div class="mcp-row mcp-last">
              <span class="mcp-label">最近检查</span>
              <span class="mcp-muted">{{ formatTime(status.last_check) }}</span>
            </div>
          </template>
        </div>

        <div class="mcp-footer">
          <button
            class="mcp-copy-config"
            type="button"
            :disabled="!status"
            @click="copy(zcodeConfig, 'config')"
          >
            {{ copied === 'config' ? '✓ 已复制' : '复制 ZCode 配置' }}
          </button>
          <button class="mcp-close-btn" type="button" @click="close">关闭</button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mcp-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
}
.mcp-btn:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.mcp-icon {
  width: 20px;
  height: 20px;
}

.mcp-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}
.mcp-panel {
  width: 460px;
  max-width: calc(100vw - 32px);
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.22);
  overflow: hidden;
}
.mcp-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-light);
}
.mcp-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.mcp-close {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.mcp-close:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.mcp-body {
  padding: 14px 18px;
  overflow-y: auto;
  flex: 1;
}
.mcp-muted {
  color: var(--text-tertiary);
  font-size: 13px;
}
.mcp-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 7px 0;
  font-size: 13px;
  color: var(--text);
}
.mcp-label {
  width: 78px;
  flex-shrink: 0;
  color: var(--text-secondary);
}
.mcp-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.mcp-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
/* 绿=运行中 / 灰=未启动 / 黄=后端不通（与 A 股惯例分离，仅表连接状态） */
.d-green {
  background: #3ba272;
}
.d-grey {
  background: #8a8f99;
}
.d-yellow {
  background: #faad14;
}
.mcp-url-wrap {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}
.mcp-url {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--text);
  background: var(--hover-bg);
  padding: 2px 6px;
  border-radius: 4px;
  word-break: break-all;
}
.mcp-copy-mini {
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 13px;
  padding: 2px 4px;
  border-radius: 4px;
}
.mcp-copy-mini:hover {
  background: var(--hover-bg);
}
.mcp-expand {
  margin-top: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--primary);
  border-radius: 6px;
  padding: 4px 12px;
  font-size: 12px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.mcp-expand:hover {
  background: var(--hover-bg);
}
.mcp-caret {
  font-size: 10px;
}
.mcp-groups {
  margin-top: 10px;
  max-height: 240px;
  overflow-y: auto;
  border: 1px solid var(--border-light);
  border-radius: 6px;
  padding: 8px 12px;
}
.mcp-group {
  padding: 6px 0;
  border-top: 1px solid var(--border-light);
}
.mcp-group:first-child {
  border-top: none;
}
.mcp-group-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: 4px;
}
.mcp-tool {
  display: flex;
  flex-direction: column;
  padding: 3px 0 3px 8px;
  border-left: 2px solid var(--border-light);
  margin-bottom: 4px;
}
.mcp-tool-name {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
  color: var(--primary);
}
.mcp-tool-desc {
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.4;
}
.mcp-last {
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid var(--border-light);
}
.mcp-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 10px 18px;
  border-top: 1px solid var(--border-light);
}
.mcp-copy-config {
  border: 1px solid var(--primary);
  background: var(--primary);
  color: #fff;
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
}
.mcp-copy-config:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mcp-close-btn {
  border: 1px solid var(--border);
  background: transparent;
  color: var(--text-secondary);
  border-radius: 6px;
  padding: 6px 14px;
  font-size: 13px;
  cursor: pointer;
}
.mcp-close-btn:hover {
  background: var(--hover-bg);
  color: var(--text);
}
</style>
