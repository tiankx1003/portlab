<script setup lang="ts">
import { ref } from 'vue'
import { deleteFeedback, listFeedback, submitFeedback, type FeedbackItem } from '../api'

const show = ref(false)
const items = ref<FeedbackItem[]>([])
const content = ref('')
const nickname = ref('')
const loading = ref(false)
const submitting = ref(false)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const r = await listFeedback()
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
  load()
}
function close() {
  show.value = false
}

async function submit() {
  const c = content.value.trim()
  if (!c) return
  submitting.value = true
  error.value = ''
  try {
    const r = await submitFeedback({ content: c, nickname: nickname.value.trim() || null })
    if (r.code !== 0) {
      error.value = r.message
      return
    }
    content.value = ''
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    submitting.value = false
  }
}

async function remove(id: number) {
  error.value = ''
  try {
    const r = await deleteFeedback(id)
    if (r.code === 0) await load()
    else error.value = r.message
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

// ---- 简易 Markdown 渲染（先 HTML 转义再替换，防 XSS）----
function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}
function renderMarkdown(src: string): string {
  let s = escapeHtml(src)
  s = s.replace(/```([\s\S]*?)```/g, (_m, c) => `<pre><code>${c}</code></pre>`) // 代码块
  s = s.replace(/`([^`]+)`/g, '<code>$1</code>') // 行内代码
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>') // 粗体
  s = s.replace(/\*([^*\n]+)\*/g, '<em>$1</em>') // 斜体
  s = s.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, // 链接（仅 http/https，防 javascript:）
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>',
  )
  s = s.replace(/\n/g, '<br>') // 换行
  return s
}

function formatTime(iso: string): string {
  // 后端存 UTC（naive），无时区后缀时按 UTC 解析再转本地展示
  const treated = /[zZ]$|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso + 'Z'
  const d = new Date(treated)
  if (isNaN(d.getTime())) return iso
  return d.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}
</script>

<template>
  <button class="feedback-btn" type="button" title="问题反馈" aria-label="问题反馈" @click="open">
    <svg class="feedback-icon" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <path
        d="M813.7 386.7v-214c0-41.4-33.5-74.9-74.9-74.9H289.2c-41.4 0-74.9 33.6-74.9 74.9v214L514 599.8l299.7-213.1zM329.6 190h368.9c12.7 0 23.1 10.3 23.1 23.1 0 12.7-10.3 23.1-23.1 23.1H329.6c-12.7 0-23.1-10.3-23.1-23.1s10.3-23.1 23.1-23.1z m-23.1 115.3c0-12.7 10.3-23.1 23.1-23.1h230.6c12.7 0 23.1 10.3 23.1 23.1 0 12.7-10.3 23.1-23.1 23.1H329.6c-12.8 0-23.1-10.4-23.1-23.1z m615 61.4L553.8 628.1l367.7 261.4c4.7-9.3 7.6-19.7 7.6-30.8V397.5c-0.1-11.1-3-21.5-7.6-30.8zM99 397.5v461.1c0 38.2 31 69.2 69.2 69.2h691.7c9.9 0 19.2-2.1 27.7-5.9l-781-555.3c-4.7 9.4-7.6 19.8-7.6 30.9z"
        fill="currentColor"
      />
    </svg>
  </button>

  <Teleport to="body">
    <div v-if="show" class="fb-overlay" @click.self="close">
      <div class="fb-panel" role="dialog" aria-modal="true" aria-label="问题反馈">
        <div class="fb-header">
          <span>问题反馈</span>
          <button class="fb-close" type="button" aria-label="关闭" @click="close">✕</button>
        </div>

        <div class="fb-body">
          <form class="fb-form" @submit.prevent="submit">
            <textarea
              v-model="content"
              class="fb-textarea"
              rows="3"
              maxlength="2000"
              placeholder="写下你的建议或问题（支持 Markdown：**粗体** *斜体* `代码` [链接](url)）"
            ></textarea>
            <div class="fb-form-row">
              <input v-model="nickname" class="fb-nick" type="text" maxlength="64" placeholder="昵称（可选）" />
              <span class="fb-count">{{ content.length }}/2000</span>
              <button type="submit" class="fb-submit" :disabled="submitting || !content.trim()">
                {{ submitting ? '提交中…' : '提交' }}
              </button>
            </div>
            <p v-if="error" class="fb-error">{{ error }}</p>
          </form>

          <div class="fb-list">
            <p v-if="loading" class="fb-empty">加载中…</p>
            <p v-else-if="!items.length" class="fb-empty">还没有反馈，快来抢沙发～</p>
            <div v-for="it in items" :key="it.id" class="fb-item">
              <div class="fb-item-head">
                <span class="fb-nick-tag">{{ it.nickname || '匿名' }}</span>
                <span class="fb-time">{{ formatTime(it.created_at) }}</span>
                <button class="fb-del" type="button" aria-label="删除" @click="remove(it.id)">✕</button>
              </div>
              <div class="fb-content" v-html="renderMarkdown(it.content)"></div>
            </div>
          </div>
        </div>

        <div class="fb-footer">反馈保留 3 天，最多显示最新 5 条</div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.feedback-btn {
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
.feedback-btn:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.feedback-icon {
  width: 20px;
  height: 20px;
}

.fb-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
}
.fb-panel {
  width: 540px;
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
.fb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  font-size: 15px;
  font-weight: 600;
  border-bottom: 1px solid var(--border-light);
  color: var(--text);
}
.fb-close {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 16px;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}
.fb-close:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.fb-body {
  padding: 16px 18px;
  overflow-y: auto;
  flex: 1;
}
.fb-textarea {
  width: 100%;
  box-sizing: border-box;
  resize: vertical;
  padding: 10px 12px;
  border: 1px solid var(--input-border);
  border-radius: 8px;
  background: var(--input-bg);
  color: var(--text);
  font-size: 13px;
  font-family: inherit;
  line-height: 1.5;
}
.fb-textarea:focus {
  outline: none;
  border-color: var(--primary);
}
.fb-form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
}
.fb-nick {
  flex: 1;
  padding: 7px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  background: var(--input-bg);
  color: var(--text);
  font-size: 13px;
}
.fb-nick:focus {
  outline: none;
  border-color: var(--primary);
}
.fb-count {
  font-size: 12px;
  color: var(--text-tertiary);
  white-space: nowrap;
}
.fb-submit {
  background: var(--primary);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 7px 18px;
  font-size: 13px;
  cursor: pointer;
}
.fb-submit:disabled {
  background: var(--primary-disabled);
  cursor: not-allowed;
}
.fb-error {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--error-text);
}
.fb-list {
  margin-top: 16px;
}
.fb-empty {
  text-align: center;
  color: var(--text-tertiary);
  font-size: 13px;
  padding: 18px 0;
}
.fb-item {
  padding: 10px 0;
  border-top: 1px solid var(--border-light);
}
.fb-item:first-child {
  border-top: none;
}
.fb-item-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}
.fb-nick-tag {
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
}
.fb-time {
  font-size: 11px;
  color: var(--text-tertiary);
}
.fb-del {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 12px;
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s, color 0.15s;
  padding: 0 4px;
}
.fb-item:hover .fb-del {
  opacity: 1;
}
.fb-del:hover {
  color: var(--error-text);
}
.fb-content {
  font-size: 13px;
  line-height: 1.6;
  color: var(--text);
  word-break: break-word;
}
.fb-footer {
  padding: 10px 18px;
  font-size: 12px;
  color: var(--text-tertiary);
  border-top: 1px solid var(--border-light);
  text-align: center;
}

/* Markdown 渲染样式（v-html 注入，需 :deep） */
.fb-content :deep(strong) {
  font-weight: 700;
}
.fb-content :deep(em) {
  font-style: italic;
}
.fb-content :deep(code) {
  padding: 1px 5px;
  border-radius: 4px;
  background: var(--hover-bg);
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 12px;
}
.fb-content :deep(pre) {
  margin: 6px 0;
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--hover-bg);
  overflow-x: auto;
}
.fb-content :deep(pre code) {
  padding: 0;
  background: transparent;
}
.fb-content :deep(a) {
  color: var(--primary);
  text-decoration: underline;
}
</style>
