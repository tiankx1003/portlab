<script setup lang="ts">
import { computed } from 'vue'
import type { Light, SignalItem } from '../api'
import LightIcon from './LightIcon.vue'
import { theme } from '../composables/useTheme'

const props = defineProps<{ item: SignalItem; clickable?: boolean }>()
const emit = defineEmits<{ click: [] }>()

const lightColor = computed(() => {
  const dark = theme.value === 'dark'
  return {
    green: dark ? '#3fb950' : '#3ba272',
    yellow: dark ? '#d29922' : '#faad14',
    red: dark ? '#f85149' : '#ee6666',
    grey: dark ? '#6e7681' : '#909399',
  } as Record<Light, string>
})

const lightShadow = computed(() => {
  const dark = theme.value === 'dark'
  const a = dark ? 0.5 : 0.35  // 暗色下阴影透明度加大才可见
  return {
    green: `rgba(63,185,80,${a})`,
    yellow: `rgba(210,153,34,${a})`,
    red: `rgba(248,81,73,${a})`,
    grey: `rgba(110,118,129,${dark ? 0.45 : 0.30})`,
  } as Record<Light, string>
})
</script>

<template>
  <div
    class="signal-card"
    :class="[props.item.light, { clickable: props.clickable }]"
    :style="props.clickable ? {
      '--card-accent': lightColor[props.item.light],
      '--card-accent-shadow': lightShadow[props.item.light],
    } : undefined"
    @click="props.clickable && emit('click')"
  >
    <div class="bar" :style="{ background: lightColor[props.item.light] }"></div>
    <div class="content">
      <div class="label">
        {{ props.item.label }}
        <LightIcon :light="props.item.light" :size="13" />
      </div>
      <div class="value">{{ props.item.display }}</div>
      <div v-if="props.item.hint" class="hint">{{ props.item.hint }}</div>
    </div>
  </div>
</template>

<style scoped>
.signal-card {
  flex: 1 1 0;
  min-width: 130px;
  display: flex;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  overflow: hidden;
  background: var(--surface);
}
.signal-card.clickable {
  cursor: pointer;
  transition: box-shadow 0.2s ease, border-color 0.2s ease;
}
.signal-card.clickable:hover {
  border-color: transparent;
  box-shadow: 0 4px 16px var(--card-accent-shadow, rgba(0, 0, 0, 0.14));
}
.bar {
  width: 4px;
  flex-shrink: 0;
}
.content {
  padding: 10px 12px;
  flex: 1;
}
.label {
  font-size: 12px;
  color: var(--text-tertiary);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.dot {
  font-size: 11px;
}
.value {
  font-size: 20px;
  font-weight: 700;
  margin-top: 4px;
  line-height: 1.2;
}
.hint {
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
</style>
