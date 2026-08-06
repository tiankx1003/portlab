<script setup lang="ts">
import type { Light } from '../api'

const props = defineProps<{ light: Light; size?: number }>()

const colors: Record<Light, { ring: string; glow: string }> = {
  green: { ring: '#3ba272', glow: '#5bc890' },
  yellow: { ring: '#faad14', glow: '#ffc53d' },
  red: { ring: '#e54d4d', glow: '#f07878' },
  grey: { ring: '#909399', glow: '#b0b3b8' },
}
</script>

<template>
  <svg
    :width="props.size ?? 14"
    :height="props.size ?? 14"
    viewBox="0 0 1024 1024"
    class="light-icon"
  >
    <path
      d="M512 512m-486.4 0a486.4 486.4 0 1 0 972.8 0 486.4 486.4 0 1 0-972.8 0Z"
      :fill="colors[props.light].glow"
    />
    <path
      d="M512 512m-435.2 0a435.2 435.2 0 1 0 870.4 0a435.2 435.2 0 1 0-870.4 0Z"
      fill="#FFFFFF"
    />
    <path
      d="M512 74.24C270.2336 74.24 74.24 270.2336 74.24 512S270.2336 949.76 512 949.76c241.7664 0 437.76-195.9936 437.76-437.76S753.7664 74.24 512 74.24z m314.7264 455.5776c-26.88 0-49.92-23.04-49.92-46.1056 0-72.9856-26.88-130.6368-80.6144-176.7424-53.7344-46.1056-111.3088-69.1712-172.7488-69.1712-30.72 0-49.8944-19.2256-49.8944-49.9456 0-26.9056 19.2-46.1056 49.8944-46.1056 92.1344 0 172.7488 30.7456 245.6832 92.2112 72.9344 61.4656 107.4944 145.9968 107.4944 249.7536 0.0256 23.04-19.1744 46.1056-49.8944 46.1056z"
      :fill="colors[props.light].ring"
    />
  </svg>
</template>

<style scoped>
.light-icon {
  flex-shrink: 0;
  display: inline-block;
}
</style>
