<template>
  <div class="favorites">
    <h2 class="page-title">我的收藏</h2>
    <div v-if="loading && !games.length" class="empty">加载中...</div>
    <div v-else-if="!games.length && !loading" class="empty">
      <p>还没有收藏游戏</p>
      <router-link to="/hot" class="go-hot">去热销榜看看吧</router-link>
    </div>
    <template v-else>
      <GameCard v-for="game in games" :key="game.id" :game="game" :show-rating="true" />
      <div ref="sentinel" class="sentinel"></div>
      <div v-if="loadingMore" class="loading-more">加载更多...</div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import GameCard from '../components/GameCard.vue'

const games = ref([])
const page = ref(1)
const total = ref(0)
const loading = ref(true)
const loadingMore = ref(false)
const sentinel = ref(null)
let observer = null

async function loadPage(p) {
  const data = await api.favorites(p, 20)
  if (p === 1) {
    games.value = data.items
  } else {
    games.value.push(...data.items)
  }
  total.value = data.total
}

onMounted(async () => {
  try { await loadPage(1) } catch {}
  loading.value = false

  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && games.value.length < total.value && !loadingMore.value) {
      loadingMore.value = true
      page.value++
      loadPage(page.value).finally(() => { loadingMore.value = false })
    }
  }, { rootMargin: '200px' })
  if (sentinel.value) observer.observe(sentinel.value)
})

onBeforeUnmount(() => { if (observer) observer.disconnect() })
</script>

<style scoped>
.favorites { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.page-title {
  font-family: var(--font-display);
  font-size: 24px; font-weight: 700; color: var(--text-primary);
  margin-bottom: 24px; letter-spacing: 1px;
}
.empty { text-align: center; padding: 60px 0; color: var(--text-muted); font-size: 16px; }
.go-hot {
  display: inline-block; margin-top: 12px;
  color: var(--neon-cyan); text-decoration: none; font-weight: 500;
}
.go-hot:hover { text-decoration: underline; }
.sentinel { height: 1px; }
.loading-more { text-align: center; padding: 20px; color: var(--text-muted); font-size: 14px; }
</style>
