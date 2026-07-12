<script setup lang="ts">
// 顶层布局：导航 + <RouterView />
</script>

<template>
  <div class="layout">
    <header class="nav">
      <div class="brand">📈 PortLab</div>
      <nav>
        <RouterLink to="/">首页</RouterLink>
      </nav>
    </header>
    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<style>
body {
  margin: 0;
  font-family: system-ui, -apple-system, 'PingFang SC', sans-serif;
  color: #1f2329;
}
.layout {
  min-height: 100vh;
}
.nav {
  display: flex;
  align-items: center;
  gap: 24px;
  padding: 12px 24px;
  border-bottom: 1px solid #eee;
  background: #fff;
}
.brand {
  font-weight: 700;
  font-size: 18px;
}
.content {
  padding: 24px;
  max-width: 1200px;
  margin: 0 auto;
}
a {
  color: #1f6feb;
  text-decoration: none;
}
a.router-link-active {
  font-weight: 600;
}
</style>
