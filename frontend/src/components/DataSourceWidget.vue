<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  clearTushareToken,
  getDataSourceStatus,
  toggleTushare,
  updateTushareToken,
  type DataSourceStatus,
} from '../api'

const REGISTER_URL = 'https://tushare.pro/register'

const show = ref(false)
const status = ref<DataSourceStatus | null>(null)
const tokenInput = ref('')
const loading = ref(false)
const saving = ref(false)
const clearing = ref(false)
const toggling = ref(false)
const error = ref('')
const info = ref('')

const enabled = computed(() => !!status.value?.tushare_enabled)
const configured = computed(() => !!status.value?.tushare_configured)
const masked = computed(() => status.value?.tushare_token_masked || '')
const activeSource = computed(() => status.value?.active_source || 'akshare')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await getDataSourceStatus()
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
  tokenInput.value = ''
  info.value = ''
  error.value = ''
  load()
}
function close() {
  show.value = false
}

// 挂载即拉取状态，使钥匙图标颜色（启用=蓝）在页面刷新后立即正确显示
onMounted(load)

async function onToggle() {
  const next = !enabled.value
  // 双重大门（前端）：开启时要求 Token 非空——已配置 或 正在输入并尚未保存
  if (next && !configured.value && !tokenInput.value.trim()) {
    error.value = '请先填写 Token 再开启'
    return
  }
  toggling.value = true
  error.value = ''
  info.value = ''
  try {
    const r = await toggleTushare(next)
    if (r.code === 0) {
      status.value = r.data
      info.value = next
        ? '已切换到 Tushare 数据源，重新发起回测即生效'
        : '已切换到免费数据源（AkShare），重新发起回测即生效'
    } else {
      error.value = r.message
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    toggling.value = false
  }
}

async function saveToken() {
  const t = tokenInput.value.trim()
  if (!t) return
  saving.value = true
  error.value = ''
  info.value = ''
  try {
    const r = await updateTushareToken({ token: t })
    if (r.code === 0) {
      status.value = r.data
      tokenInput.value = ''
      info.value = 'Token 已保存，重启服务后依然有效'
    } else {
      error.value = r.message
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    saving.value = false
  }
}

async function clearToken() {
  clearing.value = true
  error.value = ''
  info.value = ''
  try {
    const r = await clearTushareToken()
    if (r.code === 0) {
      status.value = r.data
      info.value = 'Token 已清除（开关保留原状，重新填写后可再次启用）'
    } else {
      error.value = r.message
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    clearing.value = false
  }
}
</script>

<template>
  <button
    class="datasource-btn"
    :class="{ active: enabled }"
    type="button"
    :title="enabled ? '数据源：Tushare（点击设置）' : '数据源：AkShare 免费（点击设置）'"
    aria-label="数据源设置"
    @click="open"
  >
    <svg
      class="datasource-icon"
      viewBox="0 0 1024 1024"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path d="M-664.554667 249.408" fill="currentColor" />
      <path d="M-664.554667 249.408" fill="currentColor" />
      <path
        d="M317.738667 590.122667c41.749333 0 78.08-36.330667 78.08-78.08s-36.330667-78.08-78.08-78.08-76.266667 36.330667-76.266667 78.08S275.989333 590.122667 317.738667 590.122667zM537.429333 433.962667 938.666667 433.962667l0 156.138667-78.08 0 0 154.304-154.304 0L706.282667 590.08l-168.832 0c-30.869333 90.794667-118.016 154.304-219.690667 154.304C188.821333 744.405333 85.333333 640.896 85.333333 512s103.488-232.405333 232.405333-232.405333c101.674667 0 188.821333 63.552 219.690667 154.304L537.429333 433.962667z"
        fill="currentColor"
      />
    </svg>
  </button>

  <Teleport to="body">
    <div v-if="show" class="ds-overlay" @click.self="close">
      <div class="ds-panel" role="dialog" aria-modal="true" aria-label="数据源设置">
        <div class="ds-header">
          <span>数据源设置</span>
          <span class="ds-active-tag" :class="{ tushare: enabled }">
            {{ activeSource === 'tushare' ? 'Tushare' : 'AkShare 免费' }}
          </span>
          <button class="ds-close" type="button" aria-label="关闭" @click="close">✕</button>
        </div>

        <div class="ds-body">
          <!-- 开关 -->
          <div class="ds-toggle-row">
            <div class="ds-toggle-text">
              <span class="ds-label">Tushare 数据源</span>
              <span class="ds-hint">
                {{ enabled ? '已使用 Tushare 数据源' : '已使用免费数据源（AkShare）' }}
              </span>
            </div>
            <button
              class="ds-switch"
              :class="{ on: enabled }"
              type="button"
              role="switch"
              :aria-checked="enabled"
              :disabled="toggling || loading"
              :title="enabled ? '点击关闭，回退 AkShare' : '点击启用 Tushare'"
              @click="onToggle"
            >
              <span class="ds-switch-thumb">{{ enabled ? '✓' : '' }}</span>
            </button>
          </div>

          <!-- Token -->
          <div class="ds-section">
            <span class="ds-label">Tushare Token</span>
            <div class="ds-token-row">
              <input
                v-model="tokenInput"
                class="ds-token-input"
                type="password"
                maxlength="128"
                autocomplete="off"
                :placeholder="configured ? `当前：${masked}` : '粘贴你的 Tushare Pro Token'"
              />
              <button
                class="ds-save"
                type="button"
                :disabled="saving || !tokenInput.trim()"
                @click="saveToken"
              >
                {{ saving ? '保存中…' : '保存' }}
              </button>
              <button
                class="ds-clear"
                type="button"
                :disabled="clearing || !configured"
                @click="clearToken"
              >
                {{ clearing ? '清除中…' : '清除' }}
              </button>
            </div>
            <p v-if="error" class="ds-error">{{ error }}</p>
            <p v-else-if="info" class="ds-info">{{ info }}</p>
            <p v-else-if="configured" class="ds-info">Token 已配置（{{ masked }}），重启服务后依然有效</p>
            <p v-else class="ds-hint">未配置 Token，开关仅可关闭（使用免费数据源）</p>
          </div>

          <!-- 说明 -->
          <div class="ds-note">
            Token 永久保存于本服务后端，在主动更新或清除前一直有效；关闭开关仅停用 Tushare，Token
            原样保留，可随时重新启用；服务 / 容器重启后开关与 Token 均保持。
            <a :href="REGISTER_URL" target="_blank" rel="noopener noreferrer">注册 Tushare →</a>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.datasource-btn {
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
.datasource-btn:hover {
  color: var(--text);
  background: var(--hover-bg);
}
/* 开关开启时图标高亮（primary），关闭时弱化（text-secondary）一眼可辨 */
.datasource-btn.active {
  color: var(--primary);
}
.datasource-btn.active:hover {
  color: var(--primary);
}
.datasource-icon {
  width: 20px;
  height: 20px;
}

.ds-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}
.ds-panel {
  width: 420px;
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
.ds-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid var(--border-light);
  color: var(--text);
}
.ds-active-tag {
  margin-left: 4px;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  background: var(--hover-bg);
  color: var(--text-secondary);
}
.ds-active-tag.tushare {
  background: color-mix(in srgb, var(--primary) 16%, transparent);
  color: var(--primary);
}
.ds-close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.ds-close:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.ds-body {
  padding: 16px 18px;
  overflow-y: auto;
  flex: 1;
}

/* ---- 开关行 ---- */
.ds-toggle-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  background: var(--input-bg);
}
.ds-toggle-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.ds-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.ds-hint {
  font-size: 12px;
  color: var(--text-tertiary);
}
.ds-switch {
  flex-shrink: 0;
  width: 44px;
  height: 24px;
  border-radius: 12px;
  border: 1px solid var(--border);
  background: var(--hover-bg);
  position: relative;
  cursor: pointer;
  padding: 0;
  transition: background 0.2s, border-color 0.2s;
}
.ds-switch:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.ds-switch-thumb {
  position: absolute;
  top: 1px;
  left: 1px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--primary);
  line-height: 1;
  transition: transform 0.2s;
}
.ds-switch.on {
  background: var(--primary);
  border-color: var(--primary);
}
.ds-switch.on .ds-switch-thumb {
  transform: translateX(20px);
  color: #fff;
}

/* ---- Token 区 ---- */
.ds-section {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ds-token-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ds-token-input {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  background: var(--input-bg);
  color: var(--text);
  font-size: 13px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.ds-token-input:focus {
  outline: none;
  border-color: var(--primary);
}
.ds-save {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.ds-save:disabled {
  background: var(--primary-disabled);
  cursor: not-allowed;
}
.ds-clear {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 8px 12px;
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}
.ds-clear:hover:not(:disabled) {
  color: var(--error-text);
  border-color: var(--error-border);
}
.ds-clear:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ds-error {
  margin: 0;
  font-size: 12px;
  color: var(--error-text);
}
.ds-info {
  margin: 0;
  font-size: 12px;
  color: var(--text-secondary);
}

.ds-note {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px dashed var(--border-light);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-tertiary);
}
.ds-note a {
  margin-left: 4px;
  color: var(--primary);
  text-decoration: none;
}
.ds-note a:hover {
  text-decoration: underline;
}
</style>
