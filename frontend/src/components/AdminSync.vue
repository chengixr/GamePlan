<template>
  <div class="as-wrap">
    <div class="as-cards">
      <div class="as-card">
        <span class="as-card-label">调度状态</span>
        <span class="as-card-val" :class="{ on: syncData.running }">{{ syncData.running ? '运行中' : '就绪' }}</span>
      </div>
      <div class="as-card">
        <span class="as-card-label">下次同步</span>
        <span class="as-card-val">{{ syncData.next_scheduled || '--' }}</span>
      </div>
      <div class="as-card">
        <span class="as-card-label">总游戏数</span>
        <span class="as-card-val">{{ stats.total_games }}</span>
      </div>
      <div class="as-card">
        <span class="as-card-label">今日入库</span>
        <span class="as-card-val">{{ stats.today_ranked }}</span>
      </div>
    </div>

    <div class="as-actions">
      <button class="as-btn sync-btn" @click="triggerSync" :disabled="syncing">
        {{ syncing ? '同步中...' : '手动同步' }}
      </button>
      <span class="as-msg" v-if="syncMsg">{{ syncMsg }}</span>
    </div>

    <div class="as-section" v-if="stats.daily_history?.length">
      <h3>每日入库统计</h3>
      <table class="as-table">
        <thead><tr><th>日期</th><th>入库游戏数</th></tr></thead>
        <tbody>
          <tr v-for="d in stats.daily_history" :key="d.date"><td>{{ d.date }}</td><td>{{ d.count }}</td></tr>
        </tbody>
      </table>
    </div>

    <div class="as-section">
      <h3>游戏同步状态查询</h3>
      <div class="as-search-row">
        <input v-model="gameQuery" class="as-input" placeholder="输入游戏 ID..." @keyup.enter="queryGame" />
        <button class="as-btn" @click="queryGame">查询</button>
      </div>
      <div class="as-game-info" v-if="gameInfo">
        <div class="as-info-row"><span>名称</span><span>{{ gameInfo.name }}</span></div>
        <div class="as-info-row"><span>中文名</span><span>{{ gameInfo.name_cn || '--' }}</span></div>
        <div class="as-info-row"><span>描述</span><span>{{ gameInfo.has_description ? '已同步' : '缺失' }}</span></div>
        <div class="as-info-row"><span>截图</span><span>{{ gameInfo.screenshots_count }} 张</span></div>
        <div class="as-info-row"><span>标签</span><span>{{ gameInfo.tags_count }} 个</span></div>
        <div class="as-info-row"><span>评价同步</span><span>{{ gameInfo.reviews_synced_at }}</span></div>
        <div class="as-info-row"><span>最后更新</span><span>{{ gameInfo.updated_at || '--' }}</span></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const syncData = ref({})
const stats = ref({})
const syncing = ref(false)
const syncMsg = ref('')
const gameQuery = ref('')
const gameInfo = ref(null)

async function loadData() {
  try { syncData.value = await api.adminSyncStatus() } catch {}
  try { stats.value = await api.adminSyncStats() } catch {}
}

async function triggerSync() {
  syncing.value = true
  syncMsg.value = ''
  try {
    const res = await api.adminSyncTrigger()
    syncMsg.value = res.message
  } catch (e) { syncMsg.value = '启动失败: ' + e.message }
  syncing.value = false
}

async function queryGame() {
  if (!gameQuery.value) return
  try { gameInfo.value = await api.adminSyncGame(parseInt(gameQuery.value)) }
  catch { gameInfo.value = null }
}

onMounted(() => loadData())
</script>

<style scoped>
.as-wrap { color: var(--text-primary); }
.as-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-bottom: 24px; }
.as-card {
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.05);
  border-radius: 8px;
  padding: 18px;
  display: flex; flex-direction: column; gap: 8px;
}
.as-card-label { font-size: 12px; color: var(--text-muted); letter-spacing: 1px; }
.as-card-val { font-size: 20px; font-weight: 700; font-family: var(--font-display); }
.as-card-val.on { color: #10b981; }

.as-actions { display: flex; align-items: center; gap: 14px; margin-bottom: 24px; }
.as-btn {
  padding: 8px 20px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}
.as-btn:hover { border-color: var(--neon-cyan); color: var(--neon-cyan); }
.sync-btn { background: rgba(0,229,255,0.08); border-color: rgba(0,229,255,0.2); color: var(--neon-cyan); }
.sync-btn:hover:not(:disabled) { background: rgba(0,229,255,0.15); }
.sync-btn:disabled { opacity: 0.5; cursor: default; }
.as-msg { font-size: 13px; color: var(--text-secondary); }

.as-section { margin-bottom: 28px; }
.as-section h3 { font-size: 15px; margin-bottom: 12px; font-weight: 600; }

.as-table { width: 100%; max-width: 400px; border-collapse: collapse; font-size: 13px; }
.as-table th, .as-table td { padding: 8px 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.04); }
.as-table th { color: var(--text-muted); font-weight: 500; }

.as-search-row { display: flex; gap: 10px; margin-bottom: 14px; }
.as-input {
  padding: 8px 14px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  width: 200px;
}
.as-input:focus { border-color: var(--neon-cyan); }

.as-game-info { background: var(--surface); border-radius: 8px; padding: 18px; }
.as-info-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 13px; border-bottom: 1px solid rgba(255,255,255,0.03); }
.as-info-row span:first-child { color: var(--text-muted); }
</style>
