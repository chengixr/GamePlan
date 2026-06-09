<template>
  <div class="discover-view">
    <header class="page-header">
      <h1 class="page-title">
        <span class="title-icon">&#9670;</span>
        发现
      </h1>
      <p class="page-subtitle">新游上市 · 限时特惠 · 即将发行</p>
    </header>

    <div class="games-container" :class="{ 'is-loading': isFirstLoad }">
      <div v-if="isFirstLoad" class="loading-overlay">
        <span class="loading-spinner"></span>
        <span class="loading-text">加载中...</span>
      </div>
      <GameCard
        v-for="game in games"
        :key="game.id"
        :game="game"
        :show-rating="!!auth.user"
      />
    </div>

    <div class="empty-state" v-if="!loading && !isFirstLoad && games.length === 0">
      <div class="empty-icon">&#9670;</div>
      <p>今日暂无发现内容</p>
      <p class="hint">Steam 每日同步后自动更新</p>
    </div>

    <div ref="sentinel" class="scroll-sentinel">
      <span v-if="loadingMore" class="loading-spinner small"></span>
      <span v-else-if="hasMore" class="hint-text">继续滚动加载更多</span>
      <span v-else-if="games.length > 0" class="end-text">— 共 {{ games.length }} 款，已全部加载 —</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import GameCard from '../components/GameCard.vue'
import { useAuthStore } from '../stores/auth'
import { api } from '../api'

const PAGE_SIZE = 20
const auth = useAuthStore()

const games = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(true)
const loadingMore = ref(false)
const isFirstLoad = ref(true)

const hasMore = computed(() => games.value.length < total.value)
const sentinel = ref(null)
let observer = null

function setupObserver() {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && hasMore.value && !loadingMore.value) {
      loadMore()
    }
  }, { rootMargin: '400px' })
  if (sentinel.value) observer.observe(sentinel.value)
}

async function loadPage(p, append = false) {
  const data = await api.discovery(p, PAGE_SIZE)
  if (append) {
    games.value.push(...data.items)
  } else {
    games.value = data.items
  }
  total.value = data.total
  page.value = p
}

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  observer?.disconnect()
  await loadPage(page.value + 1, true)
  loadingMore.value = false
  if (sentinel.value && observer && hasMore.value) {
    observer.observe(sentinel.value)
  }
}

onMounted(async () => {
  await auth.checkAuth()
  try { await loadPage(1) } catch {}
  loading.value = false
  isFirstLoad.value = false
  await nextTick()
  setupObserver()
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.discover-view { max-width: 900px; margin: 0 auto; padding: 24px; }

.page-header { margin-bottom: 28px; }
.page-title {
  display: flex; align-items: center; gap: 12px;
  font-family: var(--font-display);
  font-size: 28px; font-weight: 700; letter-spacing: 3px;
}
.title-icon { color: var(--neon-magenta); font-size: 18px; }
.page-subtitle {
  margin-top: 8px; font-size: 14px; color: var(--text-muted);
}

/* 首次加载覆盖层 */
.games-container { position: relative; min-height: 200px; }
.games-container.is-loading .game-card { opacity: 0.4; pointer-events: none; }
.loading-overlay {
  position: absolute; inset: 0; z-index: 10;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 16px;
  background: rgba(6,6,11,0.6); backdrop-filter: blur(4px); border-radius: 10px;
}
.loading-text { font-size: 14px; color: var(--text-muted); letter-spacing: 1px; }

.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid rgba(0,229,255,0.15);
  border-top-color: var(--neon-magenta);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.loading-spinner.small { width: 22px; height: 22px; border-width: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }

/* 滚动加载 */
.scroll-sentinel {
  display: flex; justify-content: center; align-items: center;
  padding: 32px 0; min-height: 60px;
}
.hint-text { font-size: 13px; color: var(--text-muted); opacity: 0.6; }
.end-text { font-size: 13px; color: var(--text-muted); }

/* 空状态 */
.empty-state {
  text-align: center; padding: 64px 24px;
  background: var(--surface); border: 1px solid rgba(255,255,255,0.04);
  border-radius: 10px;
}
.empty-icon { font-size: 48px; color: var(--text-muted); margin-bottom: 16px; opacity: 0.3; }
.empty-state p { font-size: 16px; color: var(--text-secondary); }
.empty-state .hint { font-size: 13px; color: var(--text-muted); margin-top: 8px; }
</style>
