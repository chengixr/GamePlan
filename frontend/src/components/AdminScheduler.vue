<template>
  <div class="sch-wrap">
    <div class="sch-header">
      <h3>定时任务列表</h3>
      <button class="sch-refresh" @click="loadJobs" :disabled="loading">刷新</button>
    </div>

    <table class="sch-table" v-if="jobs.length">
      <thead>
        <tr>
          <th>任务名称</th>
          <th>描述</th>
          <th>调度规则</th>
          <th>下次执行</th>
          <th>最近执行</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="job in jobs" :key="job.id">
          <td class="sch-name">{{ job.name }}</td>
          <td class="sch-desc">{{ job.description }}</td>
          <td class="sch-cron"><code>{{ job.cron }}</code></td>
          <td class="sch-time">{{ job.next_run || '--' }}</td>
          <td class="sch-time">{{ job.last_run || '--' }}</td>
          <td>
            <span class="sch-status" :class="job.last_status">
              <span class="sch-dot"></span>
              {{ statusLabel(job.last_status) }}
            </span>
            <span v-if="job.last_error" class="sch-error-tip" :title="job.last_error">?</span>
          </td>
          <td>
            <button
              class="sch-trigger-btn"
              :disabled="triggering === job.id"
              @click="triggerJob(job.id)"
            >{{ triggering === job.id ? '执行中...' : '立即执行' }}</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div v-else-if="!loading" class="sch-empty">暂无任务数据</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const jobs = ref([])
const loading = ref(false)
const triggering = ref(null)

function statusLabel(s) {
  const map = { success: '成功', failed: '失败', pending: '未执行' }
  return map[s] || s
}

async function loadJobs() {
  loading.value = true
  try {
    const data = await api.adminSchedulerJobs()
    jobs.value = data.jobs || []
  } catch (e) {
    console.error('加载定时任务失败:', e)
  } finally {
    loading.value = false
  }
}

async function triggerJob(jobId) {
  triggering.value = jobId
  try {
    await api.adminSchedulerTrigger(jobId)
    setTimeout(() => loadJobs(), 2000)
  } catch (e) {
    alert('触发失败: ' + e.message)
  } finally {
    triggering.value = null
  }
}

onMounted(() => loadJobs())
</script>

<style scoped>
.sch-wrap { color: var(--text-primary); }

.sch-header {
  display: flex; align-items: center; justify-content: space-between;
  margin-bottom: 20px;
}
.sch-header h3 {
  font-family: var(--font-display); font-size: 16px; font-weight: 600; letter-spacing: 2px;
}

.sch-refresh {
  padding: 6px 16px;
  font-size: 13px;
  color: var(--neon-cyan);
  background: rgba(0,229,255,0.08);
  border: 1px solid rgba(0,229,255,0.2);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}
.sch-refresh:hover { background: rgba(0,229,255,0.15); }
.sch-refresh:disabled { opacity: 0.4; cursor: not-allowed; }

.sch-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.sch-table th {
  text-align: left;
  padding: 10px 12px;
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
  letter-spacing: 0.5px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  white-space: nowrap;
}
.sch-table td {
  padding: 12px;
  border-bottom: 1px solid rgba(255,255,255,0.04);
  vertical-align: middle;
}

.sch-name { font-weight: 600; white-space: nowrap; }
.sch-desc { color: var(--text-secondary); max-width: 240px; font-size: 12px; }
.sch-cron code {
  font-size: 12px;
  background: var(--surface-raised);
  padding: 2px 8px;
  border-radius: 3px;
  color: var(--neon-amber);
  white-space: nowrap;
}
.sch-time { font-size: 12px; color: var(--text-secondary); white-space: nowrap; }

.sch-status {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 500;
}
.sch-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.sch-status.success .sch-dot { background: #10b981; }
.sch-status.success { color: #10b981; }
.sch-status.failed .sch-dot { background: var(--neon-magenta); }
.sch-status.failed { color: var(--neon-magenta); }
.sch-status.pending .sch-dot { background: var(--text-muted); }
.sch-status.pending { color: var(--text-muted); }

.sch-error-tip {
  display: inline-flex; align-items: center; justify-content: center;
  width: 16px; height: 16px;
  margin-left: 6px;
  font-size: 10px; font-weight: 700;
  color: var(--neon-magenta);
  background: rgba(255,45,120,0.15);
  border-radius: 50%;
  cursor: help;
}

.sch-trigger-btn {
  padding: 4px 12px;
  font-size: 12px;
  color: var(--text-primary);
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 4px;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.sch-trigger-btn:hover { border-color: var(--neon-cyan); color: var(--neon-cyan); }
.sch-trigger-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.sch-empty {
  text-align: center; padding: 48px 0;
  color: var(--text-muted); font-size: 14px;
}
</style>
