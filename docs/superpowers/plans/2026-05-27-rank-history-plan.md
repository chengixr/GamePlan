# 游戏历史排名查看功能 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 游戏详情页新增历史排名查看功能 — 点击按钮弹出折线图面板，支持 7/30/90 天切换

**Architecture:** 后端新增 `GET /api/games/{game_id}/rank-history` 端点查询 `daily_top_sellers` 表；前端新建 `RankHistory.vue` 组件用 Chart.js 渲染折线图，通过 `onClickOutside` 收起面板

**Tech Stack:** FastAPI + SQLAlchemy + Chart.js + vue-chartjs + Vue 3 Composition API

**Files:**
- Create: `frontend/src/components/RankHistory.vue`
- Modify: `backend/games.py` — 新增 rank-history 端点
- Modify: `frontend/src/api/index.js` — 新增 rankHistory 方法
- Modify: `frontend/src/views/GameDetail.vue` — 按钮 + 组件集成
- Install: `chart.js`, `vue-chartjs`

---

### Task 1: 安装 Chart.js 依赖

- [ ] **Step 1: 安装 chart.js 和 vue-chartjs**

```bash
cd /chenghao/claudeProject/GamePlan/frontend && npm install chart.js vue-chartjs
```

### Task 2: 后端 — 新增 rank-history API 端点

**Files:**
- Modify: `backend/games.py` — 在 `top_sellers_dates` 之后、`/{game_id}` 之前插入新端点

- [ ] **Step 1: 添加 `/games/{game_id}/rank-history` 端点**

在 `backend/games.py` 的 `top_sellers_dates` 函数之后、`/{game_id}` 路由之前（约第151行之后）插入：

```python
@router.get("/{game_id}/rank-history")
def game_rank_history(
    game_id: int,
    days: int = Query(7),
    db: Session = Depends(get_db),
):
    """查询游戏在热销榜的历史排名"""
    if days not in (7, 30, 90):
        raise HTTPException(status_code=400, detail="days 必须为 7、30 或 90")
    
    today = date.today()
    since = today - timedelta(days=days)
    
    rows = (
        db.query(DailyTopSeller)
        .filter(DailyTopSeller.game_id == game_id, DailyTopSeller.date >= since)
        .order_by(DailyTopSeller.date.asc())
        .all()
    )
    
    history = [{"date": r.date.isoformat(), "rank": r.rank} for r in rows]
    return {"game_id": game_id, "days": days, "history": history}
```

**重要**: 此路由包含路径参数 `{game_id}`，FastAPI 按注册顺序匹配，因此必须放在固定的 `/{game_id}` 路由之前（即 `@router.get("/{game_id}")` 之前）。

- [ ] **Step 2: 验证 — 启动后端测试 API**

```bash
cd /chenghao/claudeProject/GamePlan/backend && uvicorn main:app --port 8000 &
sleep 2
# 测试 7 天数据
curl -s "http://127.0.0.1:8000/api/games/1/rank-history?days=7" | python3 -m json.tool
# 测试非法 days 参数
curl -s "http://127.0.0.1:8000/api/games/1/rank-history?days=15"
# 预期: {"detail": "days 必须为 7、30 或 90"}
```

---

### Task 3: 前端 — 在 api/index.js 中添加 rankHistory 方法

**Files:**
- Modify: `frontend/src/api/index.js`

- [ ] **Step 1: 添加 rankHistory 方法**

在 `frontend/src/api/index.js` 的 `api` 对象中，`history` 方法之后添加：

```js
  rankHistory: (gameId, days = 7) => request(`/games/${gameId}/rank-history?days=${days}`),
```

---

### Task 4: 前端 — 创建 RankHistory.vue 组件

**Files:**
- Create: `frontend/src/components/RankHistory.vue`

- [ ] **Step 1: 创建 RankHistory.vue**

```vue
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
import { ref, computed, onMounted, watch, onBeforeUnmount } from 'vue'
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
```

---

### Task 5: 前端 — 集成到 GameDetail.vue

**Files:**
- Modify: `frontend/src/views/GameDetail.vue`

- [ ] **Step 1: 在 hero-meta 行添加"历史排名"按钮**

在 `hero-meta` div 中，`hero-date` 之后添加：

```vue
<button class="btn-rank-history" :class="{ active: showRankHistory }" @click.stop="toggleRankHistory">
  📈 历史排名
</button>
```

- [ ] **Step 2: 在 Hero 模块内部添加 RankHistory 面板**

在 `hero-content` 闭合 `</div>` 之后、`hero-module` 闭合 `</div>` 之前（即 hero-meta 下方）添加：

```vue
<RankHistory v-if="showRankHistory" :game-id="game.id" @close="showRankHistory = false" />
```

- [ ] **Step 3: 在 script 中添加相关代码**

```js
// import
import RankHistory from '../components/RankHistory.vue'

// reactive state (放在 rating 变量附近)
const showRankHistory = ref(false)

// toggle function
function toggleRankHistory() {
  showRankHistory.value = !showRankHistory.value
}
```

- [ ] **Step 4: 在 script 的 watch 中重置状态**

在 `watch(() => route.params.id, ...)` 回调中，与 `activeIdx.value = 0` 同行添加：

```js
showRankHistory.value = false
```

- [ ] **Step 5: 添加按钮样式**

在 `<style scoped>` 中 `.hero-date` 样式之后添加：

```css
.btn-rank-history {
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  color: var(--text-secondary);
  padding: 6px 14px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-rank-history:hover {
  color: var(--neon-cyan);
  border-color: rgba(0,229,255,0.2);
}
.btn-rank-history.active {
  background: rgba(0, 229, 255, 0.1);
  border-color: var(--neon-cyan);
  color: var(--neon-cyan);
}
```

---

### Task 6: 构建并验证

- [ ] **Step 1: 构建前端**

```bash
cd /chenghao/claudeProject/GamePlan/frontend && npm run build
```

预期：构建成功，无错误

- [ ] **Step 2: 重启后端**

```bash
pkill -f "uvicorn main:app" 2>/dev/null
cd /chenghao/claudeProject/GamePlan/backend && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
sleep 2 && curl -s http://127.0.0.1:8000/api/health
```

- [ ] **Step 3: 功能验证清单**

  1. 打开任意游戏详情页，确认 Hero 模块出现"📈 历史排名"按钮
  2. 点击按钮 → 面板展开，显示折线图和 7/30/90 天切换按钮
  3. 默认加载 7 天数据
  4. 切换 30 天/90 天 → 图表更新
  5. Y 轴第1名在顶部（反转）
  6. 再次点击按钮 → 面板收起
  7. 点击页面其他区域 → 面板收起
  8. 切换到另一个游戏详情页 → 面板自动收起

- [ ] **Step 4: 提交**

```bash
git add backend/games.py frontend/src/components/RankHistory.vue frontend/src/views/GameDetail.vue frontend/src/api/index.js frontend/package.json frontend/package-lock.json
git commit -m "feat: 游戏详情页历史排名折线图 - 7/30/90天切换"
```
