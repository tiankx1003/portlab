<script setup lang="ts">
/** 日期输入（yyyy-mm-dd 掩码 + 原生日历选择器）。

原生 <input type="date"> 在 Chrome 下年份段输满 4 位不会自动跳到月份段（要再多输
一两位才溢出），体验差且无法用 JS 改其分段光标行为。这里改用文本输入 + 手写掩码：
输 4 位自动补「-」、再 2 位再补「-」，光标随文本自然前移；右侧叠一个透明的原生
date 输入保留日历选择器。v-model 仍是 ISO「yyyy-mm-dd」字符串，与原生语义一致
（不完整/非法时为 ""）。
*/
import { ref, watch } from 'vue'

const props = defineProps<{ modelValue: string }>()
const emit = defineEmits<{ 'update:modelValue': [v: string] }>()

const display = ref(props.modelValue || '')

/** 只保留数字、最多 8 位，按 yyyy-mm-dd 插分隔符。 */
function format(raw: string): string {
  const d = raw.replace(/\D/g, '').slice(0, 8)
  if (d.length <= 4) return d
  if (d.length <= 6) return d.slice(0, 4) + '-' + d.slice(4)
  return d.slice(0, 4) + '-' + d.slice(4, 6) + '-' + d.slice(6)
}

/** 合法完整日期返回 ISO 串，否则返回 ""（与原生 date 输入一致）。 */
function validISO(s: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return ''
  const y = +m[1]
  const mo = +m[2]
  const da = +m[3]
  const dt = new Date(y, mo - 1, da)
  if (dt.getFullYear() === y && dt.getMonth() + 1 === mo && dt.getDate() === da) return s
  return ''
}

function onInput(e: Event) {
  const formatted = format((e.target as HTMLInputElement).value)
  display.value = formatted
  emit('update:modelValue', validISO(formatted))
}

function onPicker(e: Event) {
  const v = (e.target as HTMLInputElement).value
  if (!v) return
  display.value = v
  emit('update:modelValue', v)
}

// 外部更新（默认值 / 回填）→ 同步显示；自己 emit 的回环用 validISO 去重避免冲掉半截输入
watch(
  () => props.modelValue,
  (v) => {
    if (validISO(v || '') !== validISO(display.value)) display.value = v || ''
  },
)
</script>

<template>
  <div class="date-input">
    <input
      type="text"
      inputmode="numeric"
      placeholder="yyyy-mm-dd"
      maxlength="10"
      :value="display"
      @input="onInput"
    />
    <span class="cal" aria-label="选择日期">
      <svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true">
        <path
          fill="currentColor"
          d="M5 1a1 1 0 0 1 1 1v1h4V2a1 1 0 1 1 2 0v1h1a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h1V2a1 1 0 0 1 1-1M3 7v6h10V7z"
        />
      </svg>
      <input type="date" class="cal-overlay" :value="modelValue" tabindex="-1" @change="onPicker" />
    </span>
  </div>
</template>

<style scoped>
.date-input {
  display: flex;
  align-items: stretch;
  min-width: 150px;
}
.date-input input[type='text'] {
  flex: 1;
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid var(--input-border);
  border-radius: 6px 0 0 6px;
  font-size: 14px;
  background: var(--input-bg);
  color: var(--text);
  font-family: inherit;
}
.date-input input[type='text']:focus {
  outline: none;
  border-color: var(--primary);
}
.cal {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  border: 1px solid var(--input-border);
  border-left: none;
  border-radius: 0 6px 6px 0;
  background: var(--input-bg);
  color: var(--text-secondary);
  cursor: pointer;
}
.cal-overlay {
  position: absolute;
  inset: 0;
  opacity: 0;
  cursor: pointer;
}
</style>
