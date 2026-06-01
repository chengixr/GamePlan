<template>
  <div class="rec-view">
    <header class="page-header">
      <h1 class="page-title">
        <span class="title-icon">&#9670;</span>
        为你推荐
      </h1>
      <p class="page-subtitle">基于你的评分偏好 · 混合推荐算法</p>
    </header>

    <div v-if="!auth.user" class="empty-state">
      <div class="empty-icon">&#9654;</div>
      <p>请先<router-link to="/login">登录</router-link>以获取个性化推荐</p>
    </div>

    <template v-else>
      <GameCard v-for="game in store.recGames" :key="game.id" :game="game" />

      <div v-if="store.recGames.length === 0 && !loading" class="empty-state">
        <div class="empty-icon">&#9733;</div>
        <p>评分不足 · 请先在热销榜中为<span class="highlight">至少 5 款</span>游戏打分</p>
        <router-link to="/hot" class="cta-link">前往热销榜 &#8594;</router-link>
      </div>

      <!-- 无限滚动加载 -->
      <div ref="sentinel" class="scroll-sentinel">
        <span v-if="loading" class="loading-spinner"></span>
        <span v-else-if="store.recGames.length > 0 && !hasMore" class="end-text">— 已加载全部 —</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import GameCard from '../components/GameCard.vue'
import { useAuthStore } from '../stores/auth'
import { useGamesStore } from '../stores/games'

const auth = useAuthStore()
const store = useGamesStore()
const pageSize = 20
const loading = ref(true)  // 初始为 true，避免闪现"评分不足"

const sentinel = ref(null)
let observer = null

const hasMore = computed(() => store.recGames.length < store.recTotal)

function setupObserver() {
  if (observer) observer.disconnect()
  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && hasMore.value && !loading.value) {
      loadMore()
    }
  }, { rootMargin: '200px' })
  if (sentinel.value) observer.observe(sentinel.value)
}

async function loadMore() {
  if (loading.value) return
  loading.value = true
  observer?.disconnect()
  const nextPage = store.recPage + 1
  await store.loadRecommended(nextPage, pageSize, true)
  loading.value = false
  if (sentinel.value && observer && hasMore.value) {
    observer.observe(sentinel.value)
  }
}

onMounted(async () => {
  await auth.checkAuth()
  if (!auth.user) return

  const hasCache = store.recGames.length > 0
  loading.value = !hasCache

  if (!hasCache) {
    store.recGames = []
    store.recTotal = 0
  }

  await Promise.all([
    store.loadMyRatings(),
    store.loadRecommended(1, pageSize, false),
  ])
  loading.value = false
  await nextTick()
  setupObserver()
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.page-header { margin-bottom: 28px; }
.page-title {
  display: flex; align-items: center; gap: 12px;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 3px;
}
.title-icon { color: var(--neon-magenta); font-size: 18px; }
.page-subtitle {
  margin-top: 8px;
  font-size: 14px;
  color: var(--text-muted);
}

.scroll-sentinel {
  display: flex; justify-content: center; align-items: center;
  padding: 32px 0; min-height: 60px;
}
.loading-spinner {
  width: 24px; height: 24px;
  border: 2px solid transparent;
  border-top-color: var(--neon-magenta);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
.end-text { font-size: 13px; color: var(--text-muted); }

.empty-state {
  text-align: center;
  padding: 64px 24px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.04);
  border-radius: 10px;
}
.empty-icon {
  font-size: 48px;
  color: var(--text-muted);
  margin-bottom: 16px;
  opacity: 0.3;
}
.empty-state p { font-size: 16px; color: var(--text-secondary); }
.empty-state a { color: var(--neon-cyan); }
.highlight { color: var(--neon-amber); font-weight: 600; }
.cta-link {
  display: inline-block;
  margin-top: 16px;
  padding: 8px 24px;
  font-size: 14px;
  font-weight: 600;
  color: var(--void);
  background: var(--neon-cyan);
  border-radius: 4px;
  text-decoration: none;
  transition: box-shadow 0.2s;
}
.cta-link:hover { box-shadow: 0 0 16px rgba(0, 229, 255, 0.4); color: var(--void); }
</style>
