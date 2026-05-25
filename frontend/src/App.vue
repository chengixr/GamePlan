<template>
  <div class="app-wrapper">
    <div class="scanlines"></div>
    <NavBar />
    <main class="main-content">
      <router-view v-slot="{ Component }">
        <transition name="page-fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useGamesStore } from './stores/games'
import { useAuthStore } from './stores/auth'

// 启动时预加载热销榜和用户状态
const gamesStore = useGamesStore()
const authStore = useAuthStore()

onMounted(async () => {
  authStore.checkAuth()
  gamesStore.loadHot(1, 20)
import NavBar from './components/NavBar.vue'
})
</script>

<style>
:root {
  --void: #06060b;
  --surface: #0d0d1a;
  --surface-raised: #151528;
  --neon-cyan: #00e5ff;
  --neon-magenta: #ff2d78;
  --neon-amber: #ffb800;
  --text-primary: #e8e8ef;
  --text-secondary: #8a8fa6;
  --text-muted: #4a4f66;
  --border-glow: rgba(0, 229, 255, 0.15);
  --font-display: 'Orbitron', system-ui, sans-serif;
  --font-body: 'Noto Sans SC', -apple-system, sans-serif;
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  font-family: var(--font-body);
  background: var(--void);
  color: var(--text-primary);
  min-height: 100vh;
  -webkit-font-smoothing: antialiased;
}

.app-wrapper {
  position: relative;
  min-height: 100vh;
}

.scanlines {
  pointer-events: none;
  position: fixed;
  inset: 0;
  z-index: 0;
  opacity: 0.03;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0, 0, 0, 0.3) 2px,
    rgba(0, 0, 0, 0.3) 4px
  );
}

.main-content {
  position: relative;
  z-index: 1;
  max-width: 1000px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

a {
  color: var(--neon-cyan);
  text-decoration: none;
  transition: color 0.2s;
}
a:hover { color: var(--neon-magenta); }

/* 自定义滚动条 */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--void); }
::-webkit-scrollbar-thumb {
  background: var(--surface-raised);
  border-radius: 3px;
  border: 1px solid rgba(255,255,255,0.04);
}
::-webkit-scrollbar-thumb:hover { background: rgba(0, 229, 255, 0.2); }

/* Firefox scrollbar */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--surface-raised) var(--void);
}

/* Page transitions */
.page-fade-enter-active,
.page-fade-leave-active {
  transition: opacity 0.25s ease, transform 0.25s ease;
}
.page-fade-enter-from {
  opacity: 0;
  transform: translateY(12px);
}
.page-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
