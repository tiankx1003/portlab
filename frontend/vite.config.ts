import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 容器内 backend 为 compose 服务名；本地裸跑时可改为 127.0.0.1
const backendTarget = process.env.VITE_BACKEND_TARGET ?? 'http://backend:8010'

// dev server 端口（容器内外一致，docker-compose 端口映射也用它）
const port = Number(process.env.VITE_PORT) || 5173

// Vite host 白名单（绕过 DNS rebinding 防护）：逗号分隔，留空则仅允许 localhost。
// 用自定义域名/IP 访问 dev server 时需把对应 host 加入，如 'myhost,1.2.3.4'。
const allowedHosts = (process.env.VITE_ALLOWED_HOSTS ?? '')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean)

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port,
    ...(allowedHosts.length ? { allowedHosts } : {}),
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})
