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

const chartData = computed(() => ({
  labels: history.value.map(h => {
    const d = new Date(h.date)
    return `${d.getMonth() + 1}-${String(d.getDate()).padStart(2, '0')}`
  }),
  datasets: [{
    label: '排名',
    data: history.value.map(h => h.rank),
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
  }]
}))

const chartOptions = computed(() => ({
  responsive: true,
  maintainAspectRatio: false,
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
        label: (item) => `排名: 第 ${item.raw} 名`,
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
      grid: { color: 'rgba(255,255,255,0.04)' },
      ticks: {
        color: 'rgba(255,255,255,0.4)',
        font: { size: 11 },
        stepSize: 1,
        callback: (v) => `第${v}名`
      }
    }
  },
  interaction: { intersect: false, mode: 'index' }
}))

async function fetchHistory() {
  loading.value = true
  try {
    const res = await api.rankHistory(props.gameId, days.value)
    history.value = res.history || []
  } catch {
    history.value = []
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
  margin-top: 16px;
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
.rh-tabs { display: flex; gap: 6px; }
.rh-tab {
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.06);
  color: var(--text-secondary);
  padding: 4px 14px;
  border-radius: 4px;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.rh-tab:hover { color: var(--neon-cyan); border-color: rgba(0,229,255,0.2); }
.rh-tab.active {
  background: rgba(0, 229, 255, 0.1);
  border-color: var(--neon-cyan);
  color: var(--neon-cyan);
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
