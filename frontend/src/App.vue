<script setup lang="ts">
import { theme, toggleTheme } from './composables/useTheme'
</script>

<template>
  <div class="layout">
    <header class="nav">
      <div class="brand">
        <svg class="brand-logo" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path d="M742.4 192H281.6a134.4 134.4 0 0 0-134.4 134.4v371.2c0 74.24 60.16 134.4 134.4 134.4h460.8c74.24 0 134.4-60.16 134.4-134.4v-371.2c0-74.24-60.16-134.4-134.4-134.4zM281.6 256h460.8a70.4 70.4 0 0 1 70.4 70.4v371.2A70.4 70.4 0 0 1 742.4 768H281.6a70.4 70.4 0 0 1-70.4-70.4v-371.2A70.4 70.4 0 0 1 281.6 256z" fill="#FB553C"/>
          <path d="M332.8 500.6336m38.4 0l0 0q38.4 0 38.4 38.4l0 88.1664q0 38.4-38.4 38.4l0 0q-38.4 0-38.4-38.4l0-88.1664q0-38.4 38.4-38.4Z" fill="#FB553C"/>
          <path d="M614.4 444.5952m38.4 0l0 0q38.4 0 38.4 38.4l0 144.2048q0 38.4-38.4 38.4l0 0q-38.4 0-38.4-38.4l0-144.2048q0-38.4 38.4-38.4Z" fill="#FB553C"/>
          <path d="M473.6 352.4096m38.4 0l0 0q38.4 0 38.4 38.4l0 236.3904q0 38.4-38.4 38.4l0 0q-38.4 0-38.4-38.4l0-236.3904q0-38.4 38.4-38.4Z" fill="#FB553C"/>
        </svg>
        PortLab
      </div>
      <nav class="nav-links">
        <RouterLink to="/">首页</RouterLink>
        <RouterLink to="/backtest">定投回测</RouterLink>
      </nav>
      <button
        class="theme-switch"
        :class="{ dark: theme === 'dark' }"
        role="switch"
        :aria-checked="theme === 'dark'"
        :title="theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'"
        @click="toggleTheme"
      >
        <span class="thumb">{{ theme === 'dark' ? '🌙' : '☀️' }}</span>
      </button>
    </header>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
/* ---------- 主题变量 ---------- */
:root,
[data-theme='light'] {
  color-scheme: light;
  --bg: #f7f8fa;
  --surface: #ffffff;
  --input-bg: #ffffff;
  --border: #e5e6eb;
  --border-light: #eeeeee;
  --text: #1f2329;
  --text-secondary: #4e5969;
  --text-tertiary: #8a8f99;
  --hint: #86909c;
  --primary: #1f6feb;
  --primary-disabled: #9aa4b2;
  --input-border: #d9d9d9;
  --hover-bg: #f2f3f5;
  --error-bg: #fff2f0;
  --error-border: #ffccc7;
  --error-text: #d4380d;
  --shadow: rgba(0, 0, 0, 0.04);
}

[data-theme='dark'] {
  color-scheme: dark;
  --bg: #16161a;
  --surface: #232328;
  --input-bg: #1c1c20;
  --border: #34343a;
  --border-light: #2e2e34;
  --text: #e8e8ec;
  --text-secondary: #b8b8be;
  --text-tertiary: #88888f;
  --hint: #88888f;
  --primary: #4080ff;
  --primary-disabled: #55555c;
  --input-border: #3e3e44;
  --hover-bg: #2c2c32;
  --error-bg: #2a1d1d;
  --error-border: #4a2828;
  --error-text: #ff8787;
  --shadow: rgba(0, 0, 0, 0.3);
}

body {
  margin: 0;
  font-family: system-ui, -apple-system, 'PingFang SC', sans-serif;
  color: var(--text);
  background: var(--bg);
  transition: background 0.2s, color 0.2s;
}
.layout {
  min-height: 100vh;
}
.nav {
  display: flex;
  align-items: stretch;
  height: 56px;
  padding: 0 24px;
  border-bottom: 1px solid var(--border);
  background: var(--surface);
}
.brand {
  display: flex;
  align-items: center;
  font-weight: 700;
  font-size: 18px;
  padding-right: 24px;
  margin-right: 8px;
  border-right: 1px solid var(--border);
}
.brand-logo {
  width: 22px;
  height: 22px;
  margin-right: 8px;
  flex-shrink: 0;
}
.nav-links {
  display: flex;
  align-items: stretch;
  gap: 4px;
}
.nav-links a {
  display: flex;
  align-items: center;
  padding: 0 16px;
  color: var(--text-secondary);
  text-decoration: none;
  font-size: 14px;
  border-bottom: 2px solid transparent;
  transition: background 0.2s, color 0.2s;
}
.nav-links a:hover {
  background: var(--hover-bg);
  color: var(--text);
}
.nav-links a.router-link-active {
  color: var(--primary);
  font-weight: 600;
  border-bottom-color: var(--primary);
}
.content {
  padding: 24px 32px;
  max-width: 1600px;
  margin: 0 auto;
}

/* ---------- 主题开关 ---------- */
.theme-switch {
  margin-left: auto;
  align-self: center;
  width: 46px;
  height: 24px;
  border-radius: 12px;
  border: 1px solid transparent;
  background: #1f1f23; /* 日间：深色轨道，在浅色导航上清晰可见 */
  position: relative;
  cursor: pointer;
  padding: 0;
  transition: background 0.2s;
}
.theme-switch .thumb {
  position: absolute;
  top: 1px;
  left: 1px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--surface);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.25);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  line-height: 1;
  transition: transform 0.2s;
}
.theme-switch.dark {
  background: #ffffff; /* 夜间：白色轨道，在深色导航上清晰可见 */
}
.theme-switch.dark .thumb {
  transform: translateX(22px);
}
</style>
