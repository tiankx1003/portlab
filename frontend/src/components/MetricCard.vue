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
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 12px 16px;
  background: #fff;
  min-width: 130px;
}
.label {
  font-size: 12px;
  color: #8a8f99;
}
.value {
  font-size: 22px;
  font-weight: 700;
  margin-top: 4px;
  line-height: 1.2;
}
.hint {
  font-size: 11px;
  color: #8a8f99;
  margin-top: 2px;
}
</style>
