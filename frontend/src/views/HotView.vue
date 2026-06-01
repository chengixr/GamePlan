<template>
  <div class="hot-view">
    <header class="page-header">
      <div class="header-row">
        <h1 class="page-title">
          <span class="title-icon">&#9654;</span>
          {{ isHistoryMode ? `${historyDate} 热销榜` : 'Steam 今日热销榜' }}
        </h1>
        <button class="btn-history" @click="toggleSidebar">
          <span class="btn-icon">&#9783;</span>
          历史榜单
        </button>
      </div>
      <p class="page-subtitle" v-if="!isHistoryMode">实时同步 · 每日更新 · 为你发现好游戏</p>
    </header>

    <!-- 游戏列表 -->
    <div class="games-container" :class="{ 'is-loading': isFirstLoad }">
      <div v-if="isFirstLoad" class="loading-overlay">
        <span class="loading-spinner"></span>
        <span class="loading-text">加载中...</span>
      </div>
      <GameCard
        v-for="(game, idx) in displayGames"
        :key="game.id"
        :game="game"
        :rank="idx + 1"
        :show-rating="!!auth.user"
      />
    </div>

    <!-- 滚动加载 -->
    <div ref="sentinel" class="scroll-sentinel">
      <span v-if="loadingMore" class="loading-spinner small"></span>
      <span v-else-if="hasMore" class="hint-text">继续滚动加载更多</span>
      <span v-else-if="displayGames.length > 0" class="end-text">— 共 {{ displayGames.length }} 款，已全部加载 —</span>
    </div>

    <!-- 历史记录侧边栏 -->
    <teleport to="body">
      <div class="sidebar-overlay" :class="{ open: sidebarOpen }" @click.self="toggleSidebar">
        <div class="sidebar-panel" :class="{ open: sidebarOpen }">
          <div class="sidebar-header">
            <h3>历史榜单</h3>
            <button class="btn-close" @click="toggleSidebar">&times;</button>
          </div>
          <div class="sidebar-body">
            <div class="date-list-label">选择日期查看历史热销榜</div>
            <div class="calendar">
              <div class="calendar-header">
                <button class="cal-nav-btn" @click="calYear--">&#171;</button>
                <select class="cal-year-select" :value="calYear" @change="calYear=+$event.target.value">
                  <option v-for="y in yearRange" :key="y" :value="y">{{ y }}</option>
                </select>
                <button class="cal-nav-btn" @click="calMonth--">&#8249;</button>
                <select class="cal-month-select" :value="calMonth" @change="calMonth=+$event.target.value">
                  <option v-for="(m, i) in months" :key="i" :value="i+1">{{ m }}</option>
                </select>
                <button class="cal-nav-btn" @click="calMonth++">&#8250;</button>
                <button class="cal-nav-btn" @click="calYear++">&#187;</button>
              </div>
              <div class="calendar-grid">
                <span class="cal-day-head" v-for="d in weekDays" :key="d">{{ d }}</span>
                <button
                  v-for="(day, i) in calDays"
                  :key="i"
                  class="cal-day"
                  :class="{
                    empty: !day,
                    today: day === todayStr,
                    active: day === historyDate,
                    'has-data': day && availableDates.has(day),
                  }"
                  :disabled="!day || !availableDates.has(day)"
                  @click="day && availableDates.has(day) && loadHistoryDate(day)"
                >{{ day ? day.split('-')[2] : '' }}</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import GameCard from '../components/GameCard.vue'
import { useGamesStore } from '../stores/games'
import { useAuthStore } from '../stores/auth'

const PAGE_SIZE = 20
const store = useGamesStore()
const auth = useAuthStore()

const isFirstLoad = ref(true)
const loadingMore = ref(false)
const sidebarOpen = ref(false)
const isHistoryMode = ref(false)
const historyDate = ref('')

// 日历
const now = new Date()
const calYear = ref(now.getFullYear())
const calMonth = ref(now.getMonth() + 1)
const weekDays = ['日', '一', '二', '三', '四', '五', '六']
const months = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']
const todayStr = now.toISOString().slice(0, 10)
const yearRange = computed(() => {
  const minYear = store.historyDates.length > 0
    ? Math.min(...store.historyDates.map(d => parseInt(d.slice(0,4))), now.getFullYear())
    : now.getFullYear()
  const years = []
  for (let y = now.getFullYear(); y >= minYear; y--) years.push(y)
  return years
})

const availableDates = computed(() => new Set(store.historyDates))

const calDays = computed(() => {
  const firstDay = new Date(calYear.value, calMonth.value - 1, 1).getDay()
  const daysInMonth = new Date(calYear.value, calMonth.value, 0).getDate()
  const cells = []
  for (let i = 0; i < firstDay; i++) cells.push(null)
  for (let d = 1; d <= daysInMonth; d++) {
    const m = String(calMonth.value).padStart(2, '0')
    const dd = String(d).padStart(2, '0')
    cells.push(`${calYear.value}-${m}-${dd}`)
  }
  return cells
})

const displayGames = computed(() =>
  isHistoryMode.value ? store.historyGames : store.hotGames
)
const total = computed(() =>
  isHistoryMode.value ? store.historyTotal : store.hotTotal
)
const hasMore = computed(() => displayGames.value.length < total.value)

// 无限滚动
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

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  const nextPage = Math.floor(store.hotGames.length / PAGE_SIZE) + 1
  if (nextPage <= store.hotPage || !hasMore.value) {
    loadingMore.value = false
    return
  }
  observer?.disconnect()
  await store.loadHot(nextPage, PAGE_SIZE, true)
  loadingMore.value = false
  if (sentinel.value && observer && hasMore.value) {
    observer.observe(sentinel.value)
  }
}

// 侧边栏
function toggleSidebar() {
  sidebarOpen.value = !sidebarOpen.value
  if (sidebarOpen.value) {
    store.loadHistoryDates()
  }
}

async function loadHistoryDate(d) {
  historyDate.value = d
  isHistoryMode.value = true
  sidebarOpen.value = false
  isFirstLoad.value = true
  store.historyGames = []
  store.historyTotal = 0
  store.historyPage = 0
  await store.loadHistory(d, 1, PAGE_SIZE, true)
  isFirstLoad.value = false
  setupObserver()
}

// 初始化（auth 已由 router beforeEach 处理，此处仅补确认）
onMounted(async () => {
  const CACHE_TTL = 5 * 60 * 1000
  const cacheValid = store.hotCacheTime && (Date.now() - store.hotCacheTime) < CACHE_TTL && store.hotGames.length > 0

  if (cacheValid) {
    isFirstLoad.value = false
    setupObserver()
    return
  }

  isFirstLoad.value = true
  store.hotGames = []
  store.hotTotal = 0
  store.hotPage = 0

  if (!auth.user) await auth.checkAuth()
  if (auth.user) await store.loadMyRatings()

  await store.loadHot(1, PAGE_SIZE, true)
  isFirstLoad.value = false
  setupObserver()
})

onBeforeUnmount(() => {
  if (observer) observer.disconnect()
})
</script>

<style scoped>
.page-header { margin-bottom: 28px; }

/* 首次加载 */
.games-container { position: relative; min-height: 200px; }
.games-container.is-loading .game-card { opacity: 0.4; pointer-events: none; }
.loading-overlay {
  position: absolute; inset: 0; z-index: 10;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 16px;
  background: rgba(6, 6, 11, 0.6);
  backdrop-filter: blur(4px);
  border-radius: 10px;
}
.loading-text {
  font-size: 14px; color: var(--text-muted);
  letter-spacing: 1px;
}
.loading-spinner {
  width: 32px; height: 32px;
  border: 3px solid rgba(0,229,255,0.15);
  border-top-color: var(--neon-cyan);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
.loading-spinner.small { width: 22px; height: 22px; border-width: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }

.header-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-title {
  display: flex; align-items: center; gap: 12px;
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 3px;
  text-transform: uppercase;
}
.title-icon { color: var(--neon-cyan); font-size: 20px; }
.page-subtitle {
  margin-top: 8px;
  font-size: 14px;
  color: var(--text-muted);
  letter-spacing: 0.5px;
}

/* 历史记录按钮 */
.btn-history {
  display: flex; align-items: center; gap: 6px;
  padding: 8px 18px;
  font-family: var(--font-body);
  font-size: 13px; font-weight: 500;
  color: var(--text-secondary);
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 5px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}
.btn-history:hover { color: var(--neon-cyan); border-color: rgba(0,229,255,0.25); }
.btn-icon { font-size: 16px; }

/* 滚动加载 */
.scroll-sentinel {
  display: flex; justify-content: center; align-items: center;
  padding: 32px 0; min-height: 60px;
}
.hint-text { font-size: 13px; color: var(--text-muted); opacity: 0.6; }
.end-text { font-size: 13px; color: var(--text-muted); }

/* 侧边栏 */
.sidebar-overlay {
  position: fixed; inset: 0; z-index: 200;
  background: rgba(0,0,0,0.5);
  opacity: 0; pointer-events: none;
  transition: opacity 0.3s;
}
.sidebar-overlay.open { opacity: 1; pointer-events: auto; }

.sidebar-panel {
  position: fixed; top: 0; right: 0; bottom: 0;
  width: 320px; max-width: 90vw;
  background: var(--surface);
  border-left: 1px solid rgba(0,229,255,0.08);
  transform: translateX(100%);
  transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex; flex-direction: column;
}
.sidebar-panel.open { transform: translateX(0); }

.sidebar-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 24px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
}
.sidebar-header h3 {
  font-family: var(--font-display);
  font-size: 16px; font-weight: 600; letter-spacing: 2px;
}
.btn-close {
  background: none; border: none;
  font-size: 24px; color: var(--text-muted);
  cursor: pointer; padding: 0 4px; line-height: 1;
  transition: color 0.2s;
}
.btn-close:hover { color: var(--neon-magenta); }

.sidebar-body {
  flex: 1; overflow-y: auto; padding: 20px 24px;
}
.date-list-label {
  font-size: 13px; color: var(--text-muted);
  margin-bottom: 16px;
}

/* 日历 */
.calendar { width: 100%; }
.calendar-header {
  display: flex; align-items: center; justify-content: center; gap: 4px;
  margin-bottom: 14px;
}
.cal-nav-btn {
  background: var(--surface-raised); border: 1px solid rgba(255,255,255,0.08);
  color: var(--text-secondary); width: 24px; height: 28px; border-radius: 4px;
  cursor: pointer; font-size: 14px; line-height: 1;
  transition: all 0.15s; padding: 0;
}
.cal-nav-btn:hover { color: var(--neon-cyan); border-color: rgba(0,229,255,0.3); }
.cal-year-select,
.cal-month-select {
  padding: 4px 6px;
  font-family: var(--font-display); font-size: 13px; font-weight: 600;
  letter-spacing: 1px;
  color: var(--text-primary);
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px;
  cursor: pointer;
  outline: none;
  -webkit-appearance: none; appearance: none;
}
.cal-year-select option,
.cal-month-select option {
  background: var(--surface); color: var(--text-primary);
}
.cal-year-select { width: 72px; }
.cal-month-select { width: 56px; }

.calendar-grid {
  display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px;
}
.cal-day-head {
  text-align: center; font-size: 12px; font-weight: 600;
  color: var(--text-secondary);
  padding: 6px 0;
}
.cal-day {
  aspect-ratio: 1; display: flex; align-items: center; justify-content: center;
  font-family: var(--font-display); font-size: 13px; font-weight: 600;
  color: var(--text-muted);
  background: transparent; border: 1px solid transparent; border-radius: 4px;
  cursor: default; transition: all 0.12s;
}
.cal-day.has-data {
  color: var(--text-primary);
  background: var(--surface-raised);
  border-color: rgba(255,255,255,0.08);
  cursor: pointer;
}
.cal-day.has-data:hover {
  color: var(--neon-cyan);
  border-color: rgba(0,229,255,0.4);
  box-shadow: 0 0 8px rgba(0,229,255,0.1);
}
.cal-day.active {
  color: var(--void); background: var(--neon-cyan); border-color: var(--neon-cyan);
  font-weight: 700; box-shadow: 0 0 10px rgba(0,229,255,0.3);
}
.cal-day.today:not(.active) {
  border-color: rgba(255,45,120,0.5);
  color: var(--neon-magenta);
}
.cal-day.empty { background: transparent; border: none; cursor: default; }
.cal-day:disabled { opacity: 0.25; cursor: default; }
.cal-day:disabled:hover { color: var(--text-muted); border-color: transparent; box-shadow: none; }
</style>
