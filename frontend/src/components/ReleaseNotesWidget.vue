<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { listReleaseNotes, type ReleaseNoteItem, type ReleaseNoteType } from '../api'

const show = ref(false)
const items = ref<ReleaseNoteItem[]>([])
const loading = ref(false)
const error = ref('')

const TYPE_META: Record<ReleaseNoteType, { label: string; cls: string }> = {
  feature: { label: '新功能', cls: 't-feature' },
  bugfix: { label: '修复', cls: 't-bugfix' },
  improvement: { label: '优化', cls: 't-improvement' },
  notice: { label: '公告', cls: 't-notice' },
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await listReleaseNotes()
    if (r.code === 0) items.value = r.data
    else error.value = r.message
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function open() {
  show.value = true
  if (!items.value.length) load()
}
function close() {
  show.value = false
}
function retry() {
  load()
}

// 挂载时预拉一次，打开即时显示
onMounted(() => {
  load().catch(() => {
    /* 预拉失败不阻塞，打开时再重试 */
  })
})

// ---- 简易 Markdown 渲染（先 HTML 转义再替换，防 XSS；与反馈面板一致）----
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function renderMarkdown(src: string): string {
  let s = escapeHtml(src)
  s = s.replace(/```([\s\S]*?)```/g, (_m, c) => `<pre><code>${c}</code></pre>`)
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>')
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>')
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  s = s.replace(/\n/g, '<br>')
  return s
}
</script>

<template>
  <button
    class="release-btn"
    type="button"
    title="更新日志"
    aria-label="更新日志"
    @click="open"
  >
    <svg
      class="release-icon"
      viewBox="0 0 1024 1024"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <path
        d="M889.92 749.728c-1.184-1.664-119.232-165.888-119.232-287.392 0-168.448-76.16-254.784-162.688-287.008L608 160c0-52.928-43.072-96-96-96s-96 43.072-96 96l0 15.296c-86.528 32.224-162.688 118.56-162.688 287.008 0 121.216-118.016 285.248-119.2 286.88-5.408 7.456-7.36 16.928-5.312 25.952 2.048 8.96 7.872 16.672 16 21.024 5.664 3.072 107.392 57.28 233.536 84.512C399.744 947.072 452.16 992 512 992s112.256-44.928 133.632-111.296c126.112-27.104 227.84-80.992 233.504-84.032 8.16-4.352 14.016-12.032 16.064-21.024S895.328 757.184 889.92 749.728zM480 160c0-17.632 14.368-32 32-32s32 14.368 32 32l0 0.928C536.832 160.32 529.728 160 522.688 160l-21.376 0C494.272 160 487.168 160.32 480 160.928L480 160zM512 928c-22.336 0-43.136-13.408-57.984-35.296C473.216 894.72 492.608 896 512 896s38.784-1.28 57.984-3.296C555.136 914.624 534.304 928 512 928z"
        fill="currentColor"
      />
    </svg>
  </button>

  <Teleport to="body">
    <div v-if="show" class="rn-overlay" @click.self="close">
      <div class="rn-panel" role="dialog" aria-modal="true" aria-label="更新日志">
        <div class="rn-header">
          <div class="rn-title-group">
            <span class="rn-title">更新日志</span>
            <span class="rn-subtitle">最近 5 条变更</span>
          </div>
          <button class="rn-close" type="button" aria-label="关闭" @click="close">✕</button>
        </div>

        <div class="rn-body">
          <p v-if="loading" class="rn-empty">加载中…</p>
          <div v-else-if="error" class="rn-empty">
            加载失败：{{ error }}
            <button class="rn-retry" type="button" @click="retry">重试</button>
          </div>
          <p v-else-if="!items.length" class="rn-empty">暂无更新记录</p>
          <div v-for="it in items" :key="it.id" class="rn-item">
            <div class="rn-item-head">
              <span class="rn-chip" :class="TYPE_META[it.type]?.cls || 't-notice'">
                {{ TYPE_META[it.type]?.label || it.type }}
              </span>
              <span class="rn-date">{{ it.released_at }}</span>
            </div>
            <div class="rn-item-title">{{ it.title }}</div>
            <div v-if="it.detail" class="rn-detail" v-html="renderMarkdown(it.detail)"></div>
          </div>
        </div>

        <div class="rn-footer">仅展示最近 5 条变更</div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.release-btn {
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
.release-btn:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.release-icon {
  width: 20px;
  height: 20px;
}

.rn-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}
.rn-panel {
  width: 750px;
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
.rn-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border-light);
}
.rn-title-group {
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.rn-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.rn-subtitle {
  font-size: 12px;
  color: var(--text-tertiary);
}
.rn-close {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.rn-close:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.rn-body {
  padding: 8px 18px;
  overflow-y: auto;
  flex: 1;
  max-height: 60vh;
}
.rn-empty {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  padding: 28px 0;
}
.rn-retry {
  margin-left: 8px;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--primary);
  border-radius: 6px;
  padding: 2px 10px;
  font-size: 12px;
  cursor: pointer;
}
.rn-item {
  padding: 12px 0;
  border-top: 1px solid var(--border-light);
}
.rn-item:first-child {
  border-top: none;
}
.rn-item-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}
.rn-chip {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
  line-height: 1.6;
}
/* 类型标签：低饱和填色 + 深色文字（红涨绿跌惯例仅用于盈亏/涨跌，此处为类别标签） */
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
.rn-date {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}
.rn-item-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
  line-height: 1.4;
}
.rn-detail {
  margin-top: 4px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
  word-break: break-word;
}
.rn-footer {
  padding: 10px 18px;
  font-size: 12px;
  color: var(--text-tertiary);
  border-top: 1px solid var(--border-light);
  text-align: center;
}

/* Markdown 渲染样式（v-html 注入，需 :deep） */
.rn-detail :deep(strong) {
  font-weight: 700;
  color: var(--text);
}
.rn-detail :deep(em) {
  font-style: italic;
}
.rn-detail :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--hover-bg);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.rn-detail :deep(pre) {
  margin: 6px 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--hover-bg);
  overflow-x: auto;
}
.rn-detail :deep(pre code) {
  padding: 0;
  background: transparent;
}
.rn-detail :deep(a) {
  color: var(--primary);
  text-decoration: underline;
}
</style>
