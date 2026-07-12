<script setup lang="ts">
defineProps<{ label: string; value: string; color?: string; hint?: string }>()
</script>

<template>
  <div class="metric-card">
    <div class="label">{{ label }}</div>
    <div class="value" :style="color ? { color } : undefined">{{ value }}</div>
    <div v-if="hint" class="hint">{{ hint }}</div>
  </div>
</template>

<style scoped>
.metric-card {
  flex: 1 1 0;
  min-width: 120px;
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--surface);
}
.label {
  font-size: 12px;
  color: var(--text-tertiary);
}
.value {
  font-size: 22px;
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
