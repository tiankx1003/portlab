import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 容器内 backend 为 compose 服务名；本地裸跑时可改为 127.0.0.1
const backendTarget = process.env.VITE_BACKEND_TARGET ?? 'http://backend:8010'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    allowedHosts: ['ranni', '120.76.251.37'],
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})
