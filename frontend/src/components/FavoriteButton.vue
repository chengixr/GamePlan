<template>
  <button class="fav-btn" :class="{ favorited }" @click.prevent.stop="toggle" :title="favorited ? '取消收藏' : '收藏'">
    <svg viewBox="0 0 24 24" class="fav-icon">
      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
        :fill="favorited ? '#ff2d78' : 'none'"
        :stroke="favorited ? '#ff2d78' : 'currentColor'"
        stroke-width="1.5" />
    </svg>
  </button>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ gameId: Number })
const auth = useAuthStore()
const favorited = ref(false)
const loading = ref(false)

onMounted(async () => {
  if (!auth.user) return
  try {
    const data = await api.favoriteIds()
    favorited.value = data.ids.includes(props.gameId)
  } catch {}
})

async function toggle() {
  if (!auth.user || loading.value) return
  loading.value = true
  const prev = favorited.value
  favorited.value = !prev
  try {
    const data = await api.toggleFavorite(props.gameId)
    favorited.value = data.favorited
  } catch {
    favorited.value = prev
  }
  loading.value = false
}
</script>

<style scoped>
.fav-btn {
  position: absolute;
  top: 8px; right: 8px;
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(6,6,11,0.8);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  cursor: pointer;
  backdrop-filter: blur(6px);
  transition: border-color 0.2s, background 0.2s;
  z-index: 5;
}
.fav-btn:hover { border-color: rgba(255,45,120,0.4); background: rgba(255,45,120,0.1); }
.fav-btn.favorited { border-color: rgba(255,45,120,0.3); background: rgba(255,45,120,0.08); }
.fav-icon { width: 18px; height: 18px; color: var(--text-muted); transition: color 0.2s; }
.fav-btn:hover .fav-icon { color: var(--neon-magenta); }
.fav-btn.favorited .fav-icon { color: #ff2d78; }
</style>
