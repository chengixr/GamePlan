<template>
  <div class="app-wrapper">
    <div class="scanlines"></div>
    <NavBar />
    <main class="main-content">
      <router-view />
    </main>
    <Toast ref="toastRef" />
  </div>
</template>

<script setup>
import { ref, onMounted, provide } from 'vue'
import NavBar from './components/NavBar.vue'
import Toast from './components/Toast.vue'
import { useAuthStore } from './stores/auth'

const authStore = useAuthStore()
const toastRef = ref(null)
provide('toast', toastRef)

onMounted(() => {
  authStore.checkAuth()
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
  max-width: 1200px;
  margin: 0 auto;
  padding: 32px 24px 64px;
}

a {
  color: var(--neon-cyan);
  text-decoration: none;
  transition: color 0.2s;
}
a:hover { color: var(--neon-magenta); }

::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: var(--void); }
::-webkit-scrollbar-thumb {
  background: var(--surface-raised);
  border-radius: 3px;
  border: 1px solid rgba(255,255,255,0.04);
}
::-webkit-scrollbar-thumb:hover { background: rgba(0, 229, 255, 0.2); }

* {
  scrollbar-width: thin;
  scrollbar-color: var(--surface-raised) var(--void);
}

</style>
