<template>
  <div class="rank-history-panel" ref="panelRef">
    <div class="rh-header">
      <span class="rh-title">历史排名趋势</span>
      <div class="rh-tabs">
        <button
          v-for="d in [7, 30, 90]" :key="d"
          class="rh-tab"
          :class="{ active: days === d }"
          @click="switchDays(d)"
        >{{ d }}天</button>
      </div>
    </div>
    <div class="rh-chart-wrap">
      <div v-if="loading" class="rh-loading">加载中...</div>
      <div v-else-if="!history.length" class="rh-empty">暂无历史排名数据</div>
      <Line v-else :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { Line } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale, LinearScale, PointElement,
  LineElement, Title, Tooltip, Filler
} from 'chart.js'
import { api } from '../api'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Filler)

const props = defineProps({ gameId: { type: Number, required: true } })
const emit = defineEmits(['close'])

const panelRef = ref(null)
const days = ref(7)
const loading = ref(false)
const history = ref([])
const allLabels = ref([])
const allRanks = ref([])

function buildFullRange(fetched, selectedDays) {
  const today = new Date()
  const labels = []
  const ranks = []
  const rankMap = {}
  for (const h of fetched) {
    rankMap[h.date] = h.rank
  }
  for (let i = selectedDays - 1; i >= 0; i--) {
    const d = new Date(today)
    d.setDate(d.getDate() - i)
    const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    labels.push(`${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`)
    ranks.push(key in rankMap ? rankMap[key] : null)
  }
  return { labels, ranks }
}

const chartData = computed(() => ({
  labels: allLabels.value,
  datasets: [{
    label: '排名',
    data: allRanks.value,
    borderColor: '#00e5ff',
    backgroundColor: 'rgba(0, 229, 255, 0.08)',
    fill: true,
    tension: 0.3,
    pointRadius: 4,
    pointBackgroundColor: '#00e5ff',
    pointBorderColor: '#0d0d1a',
    pointBorderWidth: 2,
    pointHoverRadius: 6,
    borderWidth: 2,
    spanGaps: false,
  }]
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
  layout: {
    padding: { top: 16, right: 8, bottom: 0, left: 0 }
  },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: 'rgba(13, 13, 26, 0.95)',
      titleColor: '#00e5ff',
      bodyColor: '#e0e0e0',
      borderColor: 'rgba(0, 229, 255, 0.2)',
      borderWidth: 1,
      padding: 10,
      callbacks: {
        title: (items) => `日期: ${items[0].label}`,
        label: (item) => item.raw !== null ? `排名: 第 ${item.raw} 名` : '无数据',
      }
    }
  },
  scales: {
    x: {
      grid: { color: 'rgba(255,255,255,0.04)' },
      ticks: { color: 'rgba(255,255,255,0.4)', font: { size: 11 } }
    },
    y: {
      reverse: true,
      min: 1,
      title: {
        display: true,
        text: '排名',
        color: 'rgba(255,255,255,0.4)',
        font: { size: 12 }
      },
      grid: { color: 'rgba(255,255,255,0.04)' },
      ticks: {
        color: 'rgba(255,255,255,0.4)',
        font: { size: 11 },
        stepSize: 1,
      }
    }
  },
  interaction: { intersect: false, mode: 'index' }
}))

async function fetchHistory() {
  loading.value = true
  try {
    const res = await api.rankHistory(props.gameId, days.value)
    const fetched = res.history || []
    history.value = fetched
    const full = buildFullRange(fetched, days.value)
    allLabels.value = full.labels
    allRanks.value = full.ranks
  } catch {
    history.value = []
    const full = buildFullRange([], days.value)
    allLabels.value = full.labels
    allRanks.value = full.ranks
  } finally {
    loading.value = false
  }
}

function switchDays(d) {
  days.value = d
  fetchHistory()
}

function onClickOutside(e) {
  if (panelRef.value && !panelRef.value.contains(e.target)) {
    emit('close')
  }
}

onMounted(() => {
  fetchHistory()
  document.addEventListener('click', onClickOutside, true)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onClickOutside, true)
})
</script>

<style scoped>
.rank-history-panel {
  background: var(--surface);
  border: 1px solid rgba(0, 229, 255, 0.15);
  border-radius: 10px;
  padding: 20px;
  margin: 16px 0;
  animation: rh-slide-in 0.25s ease;
}
@keyframes rh-slide-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.rh-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.rh-title {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 2px;
  color: var(--text-primary);
}
.rh-tabs { display: flex; gap: 8px; }
.rh-tab {
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.12);
  color: var(--text-primary);
  padding: 5px 16px;
  border-radius: 4px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
}
.rh-tab:hover { color: var(--neon-cyan); border-color: rgba(0,229,255,0.3); background: rgba(0,229,255,0.05); }
.rh-tab.active {
  background: rgba(0, 229, 255, 0.12);
  border-color: var(--neon-cyan);
  color: var(--neon-cyan);
  box-shadow: 0 0 8px rgba(0,229,255,0.15);
}

.rh-chart-wrap {
  position: relative;
  height: 260px;
}

.rh-loading, .rh-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-muted);
  font-size: 14px;
}
</style>
