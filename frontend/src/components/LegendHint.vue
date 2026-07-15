<script setup lang="ts">
withDefaults(defineProps<{ text?: string }>(), {
  text: '点击图例隐藏或展示曲线',
})
</script>

<template>
  <span class="legend-hint" tabindex="0" role="img" :aria-label="text">!
    <span class="legend-hint-pop">{{ text }}</span>
  </span>
</template>

<style scoped>
.legend-hint {
  position: absolute;
  top: 0;
  right: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  cursor: help;
  z-index: 10;
  outline: none;
}
.legend-hint-pop {
  position: absolute;
  top: 22px;
  right: -4px;
  display: none;
  white-space: nowrap;
  background: var(--surface);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 400;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.15);
  z-index: 20;
}
.legend-hint:hover .legend-hint-pop,
.legend-hint:focus .legend-hint-pop {
  display: block;
}
</style>
