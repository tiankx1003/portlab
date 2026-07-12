<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getHealth, type ApiResponse } from '../api'

const health = ref<ApiResponse<{ status: string }> | null>(null)
const error = ref<string | null>(null)

onMounted(async () => {
  try {
    health.value = await getHealth()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <section>
    <h1>PortLab</h1>
    <p class="muted">个人投资分析工具箱 · 定投回测</p>

    <div class="card">
      <h3>后端健康检查</h3>
      <p v-if="error" class="err">连接失败：{{ error }}</p>
      <p v-else-if="health" class="ok">状态：{{ health.data.status }} ✓</p>
      <p v-else>检测中…</p>
    </div>
  </section>
</template>

<style scoped>
.muted {
  color: #8a8f99;
}
.card {
  border: 1px solid #eee;
  border-radius: 8px;
  padding: 16px 20px;
  max-width: 420px;
  margin-top: 16px;
}
.ok {
  color: #00a870;
  font-weight: 600;
}
.err {
  color: #d4380d;
}
</style>
