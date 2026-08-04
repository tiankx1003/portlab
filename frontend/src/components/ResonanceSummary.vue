<script setup lang="ts">
import type { Light } from '../api'

defineProps<{
  layer1: Light
  layer2: Light
  layer3: Light
  overall: string
  advice: string
}>()

const lightColor: Record<Light, string> = {
  green: '#3ba272',
  yellow: '#faad14',
  red: '#ee6666',
  grey: '#909399',
}

const lightText: Record<Light, string> = {
  green: '便宜/利好',
  yellow: '中性/观察',
  red: '昂贵/利空',
  grey: '数据不足',
}
</script>

<template>
  <div class="resonance-summary">
    <div class="layers">
      <div class="layer-item">
        <div class="layer-dot" :style="{ background: lightColor[layer1] }"></div>
        <div class="layer-text">
          <div class="layer-name">第一层 技术估值</div>
          <div class="layer-desc">{{ lightText[layer1] }}</div>
        </div>
      </div>
      <div class="layer-item">
        <div class="layer-dot" :style="{ background: lightColor[layer2] }"></div>
        <div class="layer-text">
          <div class="layer-name">第二层 大类资产</div>
          <div class="layer-desc">{{ lightText[layer2] }}</div>
        </div>
      </div>
      <div class="layer-item">
        <div class="layer-dot" :style="{ background: lightColor[layer3] }"></div>
        <div class="layer-text">
          <div class="layer-name">第三层 资金宏观</div>
          <div class="layer-desc">{{ lightText[layer3] }}</div>
        </div>
      </div>
    </div>
    <div class="overall">
      <div class="overall-status">{{ overall }}</div>
      <div class="overall-advice">{{ advice }}</div>
    </div>
  </div>
</template>

<style scoped>
.resonance-summary {
  display: flex;
  gap: 20px;
  align-items: center;
  flex-wrap: wrap;
}
.layers {
  display: flex;
  gap: 24px;
  flex: 1;
  flex-wrap: wrap;
}
.layer-item {
  display: flex;
  align-items: center;
  gap: 10px;
}
.layer-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  flex-shrink: 0;
  box-shadow: 0 0 6px rgba(0, 0, 0, 0.15);
}
.layer-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}
.layer-desc {
  font-size: 11px;
  color: var(--text-tertiary);
}
.overall {
  padding: 10px 16px;
  border-radius: 8px;
  background: var(--bg-secondary, rgba(0, 0, 0, 0.04));
  text-align: right;
}
.overall-status {
  font-size: 16px;
  font-weight: 700;
}
.overall-advice {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}
</style>
