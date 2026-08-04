<script setup lang="ts">
import type { Light, SignalItem } from '../api'

const props = defineProps<{ item: SignalItem }>()

const lightColor: Record<Light, string> = {
  green: '#3ba272',
  yellow: '#faad14',
  red: '#ee6666',
  grey: '#909399',
}

const lightLabel: Record<Light, string> = {
  green: '🟢',
  yellow: '🟡',
  red: '🔴',
  grey: '⚪',
}
</script>

<template>
  <div class="signal-card" :class="props.item.light">
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
