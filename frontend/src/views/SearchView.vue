<template>
  <div class="search-view">
    <header class="page-header">
      <form class="search-form" @submit.prevent="onSearch">
        <input
          ref="inputEl"
          v-model="query"
          class="search-input"
          placeholder="搜索游戏名称（中/英文）..."
          autofocus
        />
        <button type="submit" class="search-btn">搜索</button>
      </form>
      <p class="search-info" v-if="searched">
        "{{ searched }}" 共 {{ total }} 款结果
      </p>
    </header>

    <div v-if="loading" class="loading">搜索中...</div>

    <template v-else>
      <GameCard v-for="game in games" :key="game.id" :game="game" :show-rating="!!auth.user" />

      <div v-if="games.length === 0 && searched" class="empty-state">
        <p>未找到相关游戏</p>
        <router-link to="/hot" class="go-hot">去热销榜看看吧</router-link>
      </div>

      <div ref="sentinel" class="scroll-sentinel">
        <span v-if="loadingMore" class="loading-spinner"></span>
        <span v-else-if="hasMore" class="hint-text">继续滚动加载更多</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import GameCard from '../components/GameCard.vue'
import { useAuthStore } from '../stores/auth'
import { api } from '../api'

const route = useRoute()
const auth = useAuthStore()
const PAGE_SIZE = 20

const query = ref(route.query.q || '')
const searched = ref('')
const games = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const loadingMore = ref(false)
const inputEl = ref(null)

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

async function doSearch(p, append = false) {
  const data = await api.search(query.value.trim(), p, PAGE_SIZE)
  if (append) {
    games.value.push(...data.items)
  } else {
    games.value = data.items
  }
  total.value = data.total
  page.value = p
  searched.value = query.value.trim()
}

async function onSearch() {
  if (!query.value.trim()) return
  observer?.disconnect()
  loading.value = true
  try { await doSearch(1) } catch {}
  loading.value = false
  await nextTick()
  setupObserver()
}

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  observer?.disconnect()
  await doSearch(page.value + 1, true)
  loadingMore.value = false
  if (sentinel.value && observer && hasMore.value) {
    observer.observe(sentinel.value)
  }
}

onMounted(async () => {
  await auth.checkAuth()
  if (query.value.trim()) {
    loading.value = true
    try { await doSearch(1) } catch {}
    loading.value = false
  }
  inputEl.value?.focus()
  await nextTick()
  setupObserver()
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.search-view { max-width: 900px; margin: 0 auto; padding: 24px; }

.page-header { margin-bottom: 28px; }
.search-form { display: flex; gap: 10px; }
.search-input {
  flex: 1; padding: 12px 18px;
  font-size: 16px; font-family: var(--font-body);
  color: var(--text-primary);
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px; outline: none;
  transition: border-color 0.2s;
}
.search-input:focus { border-color: var(--neon-cyan); }
.search-input::placeholder { color: var(--text-muted); }

.search-btn {
  padding: 12px 24px;
  font-size: 14px; font-weight: 600;
  color: var(--void); background: var(--neon-cyan);
  border: none; border-radius: 6px; cursor: pointer;
  transition: box-shadow 0.2s;
}
.search-btn:hover { box-shadow: 0 0 12px rgba(0,229,255,0.3); }

.search-info { margin-top: 12px; font-size: 14px; color: var(--text-secondary); }

.loading { text-align: center; padding: 40px; color: var(--text-muted); font-size: 16px; }

.empty-state { text-align: center; padding: 60px; color: var(--text-muted); font-size: 16px; }
.go-hot { color: var(--neon-cyan); text-decoration: none; font-weight: 500; }

.scroll-sentinel {
  display: flex; justify-content: center; align-items: center;
  padding: 32px 0; min-height: 60px;
}
.hint-text { font-size: 13px; color: var(--text-muted); opacity: 0.6; }
.loading-spinner {
  width: 24px; height: 24px;
  border: 2px solid rgba(0,229,255,0.15);
  border-top-color: var(--neon-cyan);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
