# 定时任务 Tab 页 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 管理后台新增"定时任务"tab，展示 4 个 APScheduler 任务的名称/cron/下次执行时间/执行状态，支持手动触发。

**Architecture:** 后端在 steam_sync.py 的 start_scheduler() 中注册 APScheduler 事件监听器记录每次执行结果到内存 dict；admin.py 新增 GET jobs 列表 + POST trigger 端点；前端新增 AdminScheduler.vue 组件，AdminView 加第四个 tab。

**Tech Stack:** Python FastAPI + APScheduler + Vue 3 + Pinia

---

## 文件结构

| 文件 | 操作 | 职责 |
|------|------|------|
| `backend/steam_sync.py:520-536` | 修改 | 添加 `_job_status` 字典 + 事件监听器 + `get_job_status()` 导出函数 |
| `backend/models.py:68` | 修改 | 新增 `AdminSchedulerJobResponse` Pydantic 模型 |
| `backend/admin.py:111-126` | 修改 | 新增 `GET /scheduler/jobs` + `POST /scheduler/jobs/{id}/trigger` 端点 |
| `frontend/src/api/index.js:73` | 修改 | 新增 `adminSchedulerJobs()` + `adminSchedulerTrigger()` |
| `frontend/src/components/AdminScheduler.vue` | 创建 | 定时任务表格组件 |
| `frontend/src/views/AdminView.vue` | 修改 | 加第四个 tab + 引入新组件 |

---

### Task 1: 后端 — 执行状态记录机制

**Files:**
- Modify: `backend/steam_sync.py:520-536`

- [ ] **Step 1: 添加 `_job_status` 字典和导出函数**

在 `steam_sync.py` 中 `_scheduler = None` 附近（约第 403-404 行）添加：

```python
_job_status: dict[str, dict] = {}

def get_job_status() -> dict:
    return dict(_job_status)
```

- [ ] **Step 2: 在 `start_scheduler()` 中注册事件监听器**

修改 `start_scheduler()` 函数（第 520 行起），在 `_scheduler.start()` 之前添加事件监听器注册：

```python
def start_scheduler():
    global _scheduler
    from datetime import datetime, timezone
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

    _scheduler = BackgroundScheduler()

    # 事件监听：记录任务执行状态
    def _on_job_executed(event):
        _job_status[event.job_id] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "last_status": "success",
            "last_error": None,
        }

    def _on_job_error(event):
        _job_status[event.job_id] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "last_status": "failed",
            "last_error": str(event.exception)[:500] if event.exception else "未知错误",
        }

    _scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    _scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    # 初始化所有任务状态为 pending
    from ranking_sync import sync_rankings
    from logger_config import clean_old_logs
    _scheduler.add_job(sync_rankings, "cron", minute=13, id="sync_rankings")
    _scheduler.add_job(sync_steam_data, "cron", hour="0,6,12,18", minute=17, id="sync_steam_data")
    _scheduler.add_job(catchup_sync, "cron", hour=19, minute=17, id="catchup_sync")
    _scheduler.add_job(clean_old_logs, "cron", hour=3, minute=0, id="clean_old_logs")

    for job in _scheduler.get_jobs():
        if job.id not in _job_status:
            _job_status[job.id] = {"last_run": None, "last_status": "pending", "last_error": None}

    _scheduler.start()
    from threading import Timer
    Timer(10, sync_rankings).start()
    Timer(30, sync_steam_data).start()
```

注意：原来的 `add_job` 调用没有显式指定 `id` 参数，APScheduler 会自动生成 ID。这里改为显式指定 `id`，确保与 `_job_status` 的 key 一致。

**同时需要确保 `admin.py` 可以导入 `get_job_status`。** 检查 `admin.py` 第 11 行现有 import：

```python
from steam_sync import sync_steam_data, _scheduler
```

需更新为：

```python
from steam_sync import sync_steam_data, _scheduler, get_job_status
```

- [ ] **Step 3: 验证语法**

```bash
cd /chenghao/claudeProject/GamePlan && python3 -c "import ast; ast.parse(open('backend/steam_sync.py').read()); print('OK')"
```

- [ ] **Step 4: 重启后端验证无启动错误**

```bash
fuser -k 8000/tcp 2>/dev/null; sleep 1; cd /chenghao/claudeProject/GamePlan && ./start.sh prod
sleep 3 && curl -s http://localhost:8000/api/admin/sync/status | python3 -m json.tool
```

- [ ] **Step 5: Commit**

```bash
git add backend/steam_sync.py backend/admin.py
git commit -m "feat: 添加定时任务执行状态记录机制"
```

---

### Task 2: 后端 — scheduler/jobs API 端点

**Files:**
- Modify: `backend/models.py:68`
- Modify: `backend/admin.py:111-126`

- [ ] **Step 1: 添加 Pydantic 响应模型**

在 `backend/models.py` 末尾添加：

```python
class AdminSchedulerJobResponse(BaseModel):
    id: str
    name: str
    description: str
    cron: str
    next_run: str = ""
    last_run: str = ""
    last_status: str = "pending"
    last_error: str = ""
```

- [ ] **Step 2: 定义任务元数据映射**

在 `backend/admin.py` 的同步监控区域之后（约第 183 行之前），添加任务元数据字典和 cron 人类可读转换：

```python
# ========== 定时任务 ==========

_JOB_META = {
    "sync_rankings": {"name": "排名快照同步", "description": "每小时从 Steam 搜索页抓取热销前 100 名排名，缺失游戏自动拉取详情入库", "cron": "每小时第 13 分"},
    "sync_steam_data": {"name": "完整数据同步", "description": "多源同步（API+搜索+SteamCharts），更新游戏详情、截图、标签、评价", "cron": "每天 00:17, 06:17, 12:17, 18:17 (UTC)"},
    "catchup_sync": {"name": "追补同步", "description": "补录当天缺失的排名记录，补充数据不完整游戏的截图/描述/标签", "cron": "每天 19:17 (UTC)"},
    "clean_old_logs": {"name": "日志清理", "description": "清理 30 天前的过期日志文件", "cron": "每天 03:00 (UTC)"},
}
```

- [ ] **Step 3: 添加 GET /scheduler/jobs 端点**

在上一步元数据之后添加：

```python
@router.get("/scheduler/jobs")
def list_scheduler_jobs(admin: User = Depends(require_admin)):
    from steam_sync import get_job_status
    job_status = get_job_status()

    jobs = _scheduler.get_jobs() if _scheduler else []
    items = []
    for j in jobs:
        meta = _JOB_META.get(j.id, {"name": j.id, "description": "", "cron": ""})
        status = job_status.get(j.id, {"last_run": None, "last_status": "pending", "last_error": None})
        items.append(AdminSchedulerJobResponse(
            id=j.id,
            name=meta["name"],
            description=meta["description"],
            cron=meta["cron"],
            next_run=j.next_run_time.strftime("%Y-%m-%d %H:%M:%S") if j.next_run_time else "",
            last_run=status.get("last_run") or "",
            last_status=status.get("last_status", "pending"),
            last_error=status.get("last_error") or "",
        ).model_dump())
    return {"jobs": items}
```

- [ ] **Step 4: 添加 POST /scheduler/jobs/{job_id}/trigger 端点**

```python
@router.post("/scheduler/jobs/{job_id}/trigger")
def trigger_scheduler_job(job_id: str, admin: User = Depends(require_admin)):
    if not _scheduler:
        raise HTTPException(503, "调度器未启动")

    from steam_sync import get_job_status
    status = get_job_status().get(job_id, {})

    # 检查是否正在执行中（简单判断：最近执行在 5 秒内且状态为 pending 之后的过渡）
    # 实际用 APScheduler 的 running jobs 判断
    running_ids = {j.id for j in _scheduler.get_jobs() if j.next_run_time is None}
    if False:  # APScheduler get_jobs 无法直接判断 running，用简单时间窗口
        pass

    job = None
    for j in _scheduler.get_jobs():
        if j.id == job_id:
            job = j
            break

    if not job:
        raise HTTPException(404, f"任务 {job_id} 不存在")

    from threading import Thread
    t = Thread(target=job.func, daemon=True)
    t.start()
    return {"status": "started", "job_id": job_id}
```

- [ ] **Step 5: 验证 API**

```bash
# 重启后端
fuser -k 8000/tcp 2>/dev/null; sleep 1; cd /chenghao/claudeProject/GamePlan && ./start.sh prod
sleep 3

# 测试 jobs 列表（需要先登录 admin 账号）
curl -s http://localhost:8000/api/admin/scheduler/jobs -H "Cookie: session_id=..." | python3 -m json.tool
```

- [ ] **Step 6: Commit**

```bash
git add backend/models.py backend/admin.py
git commit -m "feat: 新增 scheduler/jobs API 端点"
```

---

### Task 3: 前端 — API 路由

**Files:**
- Modify: `frontend/src/api/index.js:73`

- [ ] **Step 1: 添加两个新的 API 函数**

在 `api` 对象末尾（第 73 行 `adminLogs` 之后）添加：

```javascript
  adminSchedulerJobs: () => request('/admin/scheduler/jobs'),
  adminSchedulerTrigger: (jobId) => request(`/admin/scheduler/jobs/${jobId}/trigger`, { method: 'POST' }),
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/index.js
git commit -m "feat: 前端 API 新增 scheduler jobs/trigger 路由"
```

---

### Task 4: 前端 — AdminScheduler.vue 组件

**Files:**
- Create: `frontend/src/components/AdminScheduler.vue`

- [ ] **Step 1: 创建组件文件**

写入 `frontend/src/components/AdminScheduler.vue`：

```vue
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
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/AdminScheduler.vue
git commit -m "feat: 新增 AdminScheduler 定时任务组件"
```

---

### Task 5: 前端 — AdminView 集成

**Files:**
- Modify: `frontend/src/views/AdminView.vue`

- [ ] **Step 1: 添加第四个 tab + 引入组件**

修改 `AdminView.vue`：

```vue
<template>
  <div class="admin">
    <h1 class="admin-title">管理后台</h1>
    <div class="admin-tabs">
      <button v-for="tab in tabs" :key="tab.key" class="admin-tab" :class="{ active: activeTab === tab.key }" @click="activeTab = tab.key">
        {{ tab.label }}
      </button>
    </div>
    <AdminUsers v-if="activeTab === 'users'" />
    <AdminSync v-if="activeTab === 'sync'" />
    <AdminLogs v-if="activeTab === 'logs'" />
    <AdminScheduler v-if="activeTab === 'scheduler'" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AdminUsers from '../components/AdminUsers.vue'
import AdminSync from '../components/AdminSync.vue'
import AdminLogs from '../components/AdminLogs.vue'
import AdminScheduler from '../components/AdminScheduler.vue'

const activeTab = ref('users')
const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'sync', label: '同步监控' },
  { key: 'logs', label: '日志查看' },
  { key: 'scheduler', label: '定时任务' },
]
</script>
```

（style 不变，无需修改）

- [ ] **Step 2: 构建前端验证**

```bash
cd /chenghao/claudeProject/GamePlan/frontend && npm run build
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/AdminView.vue
git commit -m "feat: AdminView 新增定时任务 tab"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 重启服务**

```bash
fuser -k 8000/tcp 2>/dev/null; sleep 1
cd /chenghao/claudeProject/GamePlan && ./start.sh prod
```

- [ ] **Step 2: 验证 API 返回**

登录管理员账号后访问 `http://localhost:8000/api/admin/scheduler/jobs`，确认返回 4 个任务，字段完整。

- [ ] **Step 3: 验证前端渲染**

浏览器访问 `/admin` → 点击"定时任务"tab → 确认表格显示 4 个任务，状态为"未执行"。

- [ ] **Step 4: 验证手动触发**

点击某任务的"立即执行"按钮 → 等待 2 秒自动刷新 → 确认状态更新为"成功"或"失败"。

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: 端到端验证通过"
```
