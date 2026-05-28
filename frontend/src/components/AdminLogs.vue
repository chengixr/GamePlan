<template>
  <div class="al-wrap">
    <div class="al-toolbar">
      <div class="al-control">
        <label>日期</label>
        <input v-model="logDate" type="text" class="al-input" placeholder="YYYY-MM-DD 留空=今天" />
      </div>
      <div class="al-control">
        <label>级别</label>
        <select v-model="logLevel" class="al-select">
          <option>ALL</option>
          <option>INFO</option>
          <option>WARNING</option>
          <option>ERROR</option>
        </select>
      </div>
      <div class="al-control">
        <label>行数</label>
        <select v-model="logLines" class="al-select">
          <option :value="50">50</option>
          <option :value="100">100</option>
          <option :value="200">200</option>
        </select>
      </div>
      <button class="al-btn" @click="loadLogs">查询</button>
      <label class="al-auto">
        <input type="checkbox" v-model="autoRefresh" /> 自动刷新
      </label>
    </div>

    <div class="al-info">
      <span>文件: {{ logFile }}</span>
      <span>共 {{ logTotal }} 行，显示最近 {{ logLines }} 行</span>
    </div>

    <div class="al-log-box" ref="logBox">
      <div v-if="loading" class="al-log-loading">加载中...</div>
      <pre v-else>{{ logs }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'

const logDate = ref('')
const logLevel = ref('ALL')
const logLines = ref(100)
const autoRefresh = ref(false)
const logs = ref('')
const logFile = ref('')
const logTotal = ref(0)
const loading = ref(false)
const logBox = ref(null)

let timer = null

async function loadLogs() {
  loading.value = true
  try {
    const res = await api.adminLogs(logDate.value, logLevel.value, logLines.value)
    logs.value = res.lines.join('\n') || '(无日志)'
    logFile.value = res.file
    logTotal.value = res.total
    setTimeout(() => {
      if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
    }, 50)
  } catch { logs.value = '(加载失败)' }
  finally { loading.value = false }
}

watch(autoRefresh, (v) => {
  if (timer) { clearInterval(timer); timer = null }
  if (v) { timer = setInterval(loadLogs, 5000) }
})

onMounted(() => loadLogs())
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style scoped>
.al-wrap { color: var(--text-primary); }
.al-toolbar { display: flex; align-items: flex-end; gap: 14px; margin-bottom: 14px; flex-wrap: wrap; }
.al-control { display: flex; flex-direction: column; gap: 4px; }
.al-control label { font-size: 11px; color: var(--text-muted); letter-spacing: 1px; }
.al-input {
  width: 160px; padding: 7px 12px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 5px;
  color: var(--text-primary); font-size: 13px;
  outline: none;
}
.al-input:focus { border-color: var(--neon-cyan); }
.al-select {
  padding: 7px 10px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 5px;
  color: var(--text-primary); font-size: 13px;
  outline: none; cursor: pointer;
}
.al-btn {
  padding: 7px 18px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 5px;
  color: var(--text-primary);
  font-size: 13px; cursor: pointer;
  transition: all 0.15s;
}
.al-btn:hover { border-color: var(--neon-cyan); color: var(--neon-cyan); }
.al-auto { display: flex; align-items: center; gap: 6px; font-size: 13px; color: var(--text-secondary); cursor: pointer; }

.al-info { display: flex; gap: 20px; font-size: 12px; color: var(--text-muted); margin-bottom: 10px; }

.al-log-box {
  background: #06060b;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 8px;
  padding: 16px;
  height: 500px;
  overflow-y: auto;
  overflow-x: auto;
}
.al-log-box pre {
  margin: 0;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  line-height: 1.7;
  color: #a0a8c0;
  white-space: pre;
}
.al-log-loading { color: var(--text-muted); text-align: center; padding: 40px; }
</style>
