<script setup lang="ts">
import { theme, toggleTheme } from './composables/useTheme'
import { GITHUB_REPO } from './config'
import DataSourceWidget from './components/DataSourceWidget.vue'
import FeedbackWidget from './components/FeedbackWidget.vue'
import McpStatusWidget from './components/McpStatusWidget.vue'
import ReleaseNotesWidget from './components/ReleaseNotesWidget.vue'
</script>

<template>
  <div class="layout">
    <header class="nav">
      <RouterLink to="/" class="brand" title="返回首页">
        <svg class="brand-logo" viewBox="0 0 1024 1024" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
          <path d="M742.4 192H281.6a134.4 134.4 0 0 0-134.4 134.4v371.2c0 74.24 60.16 134.4 134.4 134.4h460.8c74.24 0 134.4-60.16 134.4-134.4v-371.2c0-74.24-60.16-134.4-134.4-134.4zM281.6 256h460.8a70.4 70.4 0 0 1 70.4 70.4v371.2A70.4 70.4 0 0 1 742.4 768H281.6a70.4 70.4 0 0 1-70.4-70.4v-371.2A70.4 70.4 0 0 1 281.6 256z" fill="#FB553C"/>
          <path d="M332.8 500.6336m38.4 0l0 0q38.4 0 38.4 38.4l0 88.1664q0 38.4-38.4 38.4l0 0q-38.4 0-38.4-38.4l0-88.1664q0-38.4 38.4-38.4Z" fill="#FB553C"/>
          <path d="M614.4 444.5952m38.4 0l0 0q38.4 0 38.4 38.4l0 144.2048q0 38.4-38.4 38.4l0 0q-38.4 0-38.4-38.4l0-144.2048q0-38.4 38.4-38.4Z" fill="#FB553C"/>
          <path d="M473.6 352.4096m38.4 0l0 0q38.4 0 38.4 38.4l0 236.3904q0 38.4-38.4 38.4l0 0q-38.4 0-38.4-38.4l0-236.3904q0-38.4 38.4-38.4Z" fill="#FB553C"/>
        </svg>
        PortLab
      </RouterLink>
      <nav class="nav-links">
        <RouterLink to="/backtest">定投回测</RouterLink>
        <RouterLink to="/ma120">MA120 策略</RouterLink>
        <RouterLink to="/drawboard">回撤看板</RouterLink>
        <RouterLink to="/grid">网格交易</RouterLink>
        <RouterLink to="/portfolio">组合回测</RouterLink>
        <RouterLink to="/arena">策略擂台</RouterLink>
        <RouterLink to="/etf-flow">ETF 流向</RouterLink>
        <RouterLink to="/valuation">估值</RouterLink>
        <RouterLink to="/event">事件看板</RouterLink>
      </nav>
      <div class="nav-actions">
        <McpStatusWidget />
        <DataSourceWidget />
        <FeedbackWidget />
        <ReleaseNotesWidget />
        <a
          class="nav-icon-btn github-link"
          :href="GITHUB_REPO"
          target="_blank"
          rel="noopener noreferrer"
          title="GitHub 仓库"
          aria-label="GitHub 仓库"
        >
          <svg
            class="github-icon"
            viewBox="0 0 1024 1024"
            xmlns="http://www.w3.org/2000/svg"
            aria-hidden="true"
          >
            <path
              d="M511.6 76.3C264.3 76.2 64 276.4 64 523.5 64 718.9 189.3 885 363.8 946c23.5 5.9 19.9-10.8 19.9-22.2v-77.5c-135.7 15.9-141.2-73.9-150.3-88.9C215 726 171.5 718 184.5 703c30.9-15.9 62.4 4 98.9 57.9 26.4 39.1 77.9 32.5 104 26 5.7-23.5 17.9-44.5 34.7-60.8-140.6-25.2-199.2-111-199.2-213 0-49.5 16.3-95 48.3-131.7-20.4-60.5 1.9-112.3 4.9-120 58.1-5.2 118.5 41.6 123.2 45.3 33-8.9 70.7-13.6 112.9-13.6 42.4 0 80.2 4.9 113.5 13.9 11.3-8.6 67.3-48.8 121.3-43.9 2.9 7.7 24.7 58.3 5.5 118 32.4 36.8 48.9 82.7 48.9 132.3 0 102.2-59 188.1-200 212.9 23.5 23.2 38.1 55.4 38.1 91v112.5c0.8 9 0 17.9 15 17.9 177.1-59.7 304.6-227 304.6-424.1 0-247.2-200.4-447.3-447.5-447.3z"
              fill="currentColor"
            />
          </svg>
        </a>
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
      </div>
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
  text-decoration: none;
  color: var(--text);
  cursor: pointer;
  transition: color 0.2s;
}
.brand:hover {
  color: var(--primary);
}
/* 主页态（router-link-active）不加下划线 / 不变 primary，区别于功能页 */
.brand.router-link-active {
  color: var(--text);
  border-bottom: none;
}
.brand-logo {
  width: 30px;
  height: 30px;
  margin-right: 10px;
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
.nav-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 12px;
}
.content {
  padding: 24px 32px;
  max-width: 1600px;
  margin: 0 auto;
}

/* ---------- 导航栏外链图标按钮（GitHub 等） ---------- */
.nav-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--text-secondary);
  cursor: pointer;
  transition: color 0.2s, background 0.2s;
}
.nav-icon-btn:hover {
  color: var(--text);
  background: var(--hover-bg);
}
.github-icon {
  width: 20px;
  height: 20px;
}

/* ---------- 主题开关 ---------- */
.theme-switch {
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
