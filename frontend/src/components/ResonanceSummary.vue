<script setup lang="ts">
import type { Light } from '../api'

defineProps<{
  layers: { light: Light; name: string; desc: string }[]
  overall: string
  advice: string
}>()

const lightColor: Record<Light, string> = {
  green: '#3ba272',
  yellow: '#faad14',
  red: '#ee6666',
  grey: '#909399',
}
</script>

<template>
  <div class="resonance-summary">
    <div class="layers">
      <div v-for="(layer, i) in layers" :key="i" class="layer-item">
        <span class="layer-dot" :style="{ background: lightColor[layer.light] }"></span>
        <span class="layer-name">{{ layer.name }}</span>
      </div>
    </div>
    <div class="overall">
      <span class="overall-status">{{ overall }}</span>
      <span class="overall-advice">{{ advice }}</span>
    </div>
  </div>
</template>

<style scoped>
.resonance-summary {
  display: flex;
  align-items: flex-end;
  gap: 24px;
  flex-wrap: wrap;
}
.layers {
  display: flex;
  gap: 20px;
  flex-wrap: nowrap;
  align-items: flex-end;
}
.layer-item {
  display: flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}
.layer-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  display: inline-block;
}
.layer-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.overall {
  margin-left: auto;
  text-align: right;
  white-space: nowrap;
}
.overall-status {
  font-size: 16px;
  font-weight: 700;
  margin-right: 10px;
}
.overall-advice {
  font-size: 12px;
  color: var(--text-tertiary);
}
</style>
