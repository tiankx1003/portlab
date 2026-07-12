import { ref } from 'vue'

export type Theme = 'light' | 'dark'

function detectInitial(): Theme {
  try {
    const stored = localStorage.getItem('theme') as Theme | null
    if (stored === 'light' || stored === 'dark') return stored
    if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
      return 'dark'
    }
  } catch {
    /* ignore */
  }
  return 'light'
}

export const theme = ref<Theme>(detectInitial())

export function applyTheme(t: Theme): void {
  theme.value = t
  try {
    document.documentElement.setAttribute('data-theme', t)
    localStorage.setItem('theme', t)
  } catch {
    /* ignore */
  }
}

export function toggleTheme(): void {
  applyTheme(theme.value === 'dark' ? 'light' : 'dark')
}

// 兜底：确保 DOM 属性与初始值一致（index.html 已提前设置，避免闪烁）
try {
  document.documentElement.setAttribute('data-theme', theme.value)
} catch {
  /* ignore */
}
