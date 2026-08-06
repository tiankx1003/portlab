<script setup lang="ts">
import type { Light, SignalItem } from '../api'

const props = defineProps<{ item: SignalItem; clickable?: boolean }>()
const emit = defineEmits<{ click: [] }>()

const lightColor: Record<Light, string> = {
  green: '#3ba272',
  yellow: '#faad14',
  red: '#ee6666',
  grey: '#909399',
}

// 带 35% 透明度的同色，用于阴影
const lightShadow: Record<Light, string> = {
  green: 'rgba(59,162,114,0.35)',
  yellow: 'rgba(250,173,20,0.35)',
  red: 'rgba(238,102,102,0.35)',
  grey: 'rgba(144,147,153,0.30)',
}

const lightLabel: Record<Light, string> = {
  green: '🟢',
  yellow: '🟡',
  red: '🔴',
  grey: '⚪',
}
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
        <span class="dot">{{ lightLabel[props.item.light] }}</span>
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
