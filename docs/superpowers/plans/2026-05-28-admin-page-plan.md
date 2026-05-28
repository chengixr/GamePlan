# 管理后台页面 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现管理后台 `/admin` 页面，包含用户管理、同步监控、日志查看三大功能

**Architecture:** 后端新增 `admin.py` 路由模块（9 个端点，全部依赖 `require_admin`），数据库 User 模型加 `is_admin`/`is_active` 字段，前端 4 个组件（AdminView + 3 个 Tab 子组件）

**Tech Stack:** FastAPI + SQLAlchemy + Vue 3 + Pinia

**Files:**
- Create: `backend/admin.py`, `frontend/src/views/AdminView.vue`, `frontend/src/components/AdminUsers.vue`, `frontend/src/components/AdminSync.vue`, `frontend/src/components/AdminLogs.vue`
- Modify: `backend/database.py`, `backend/auth.py`, `backend/models.py`, `backend/main.py`, `frontend/src/router/index.js`, `frontend/src/components/NavBar.vue`, `frontend/src/stores/auth.js`, `frontend/src/api/index.js`

---

### Task 1: 数据库 User 模型扩展

**Files:** Modify `backend/database.py:26-33`

- [ ] **Step 1: 在 User 模型中添加 is_admin 和 is_active 字段**

```python
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    nickname = Column(String(50), default="")
    password_hash = Column(String(128), nullable=False)
    avatar = Column(String(10), default="1")
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

注意：`Boolean` 需要从 sqlalchemy 导入，已在文件头 `Column` 旁添加。

- [ ] **Step 2: 重启后端验证 schema 自动升级**

```bash
pkill -f "uvicorn main:app" 2>/dev/null
cd /chenghao/claudeProject/GamePlan/backend && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
sleep 3 && curl -s http://127.0.0.1:8000/api/health
```

预期：`{"status":"ok"}`，新字段自动添加到数据库

- [ ] **Step 3: 设置第一个管理员用户**

```bash
cd /chenghao/claudeProject/GamePlan/backend && python3 -c "
from database import SessionLocal, User
db = SessionLocal()
u = db.query(User).filter(User.username == 'chengixr').first()
if u:
    u.is_admin = True
    db.commit()
    print(f'用户 {u.username} 已设为管理员')
else:
    print('未找到用户')
db.close()
"
```

- [ ] **Step 4: 提交**

```bash
git add backend/database.py
git commit -m "feat: User模型添加is_admin和is_active字段"
```

---

### Task 2: 后端 Models 扩展 + Auth 中间件

**Files:** Modify `backend/models.py`, `backend/auth.py`

- [ ] **Step 1: 扩展 UserResponse 模型，添加 AdminUserResponse**

在 `backend/models.py` 末尾添加：

```python
class AdminUserResponse(BaseModel):
    id: int
    username: str
    nickname: str
    avatar: str = "1"
    is_active: bool = True
    rating_count: int = 0
    created_at: str = ""

class AdminSyncStatusResponse(BaseModel):
    running: bool
    last_complete: str = ""
    next_scheduled: str = ""

class AdminLogResponse(BaseModel):
    lines: list[str]
    total: int
```

- [ ] **Step 2: UserResponse 添加 is_admin 字段**

修改 `backend/models.py` 的 `UserResponse`：

```python
class UserResponse(BaseModel):
    id: int
    username: str
    nickname: str = ""
    avatar: str = "1"
    is_admin: bool = False
```

- [ ] **Step 3: auth.py 添加 require_admin 依赖**

在 `backend/auth.py` 的 `get_current_user` 函数之后添加：

```python
def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return current_user
```

- [ ] **Step 4: 修改 auth.py 的 _user_response 函数，返回 is_admin**

```python
def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, username=user.username,
        nickname=user.nickname or user.username,
        avatar=user.avatar or "1",
        is_admin=user.is_admin or False
    )
```

- [ ] **Step 5: 提交**

```bash
git add backend/models.py backend/auth.py
git commit -m "feat: UserResponse加is_admin+require_admin中间件+AdminModels"
```

---

### Task 3: 后端 Admin API 模块

**Files:** Create `backend/admin.py`

- [ ] **Step 1: 创建 backend/admin.py**

```python
import os
import json
import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, User, Rating, Game, DailyTopSeller, UserSession
from models import AdminUserResponse, AdminSyncStatusResponse, AdminLogResponse
from auth import require_admin, get_db
from steam_sync import sync_steam_data, _scheduler

logger = logging.getLogger("admin")
router = APIRouter()
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")

# ========== 用户管理 ==========

@router.get("/users")
def list_users(
    search: str = Query("", max_length=50),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    q = db.query(User)
    if search:
        q = q.filter(User.username.contains(search) | User.nickname.contains(search))
    total = q.count()
    users = q.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for u in users:
        count = db.query(func.count(Rating.id)).filter(Rating.user_id == u.id).scalar()
        items.append(AdminUserResponse(
            id=u.id, username=u.username, nickname=u.nickname or u.username,
            avatar=u.avatar or "1", is_active=u.is_active, rating_count=count,
            created_at=u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else ""
        ).model_dump())
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.put("/users/{user_id}/status")
def toggle_user_status(
    user_id: int,
    body: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能禁用自己")
    user.is_active = body.get("is_active", True)
    db.commit()
    return {"status": "ok", "is_active": user.is_active}

@router.delete("/users/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能删除自己")
    db.query(Rating).filter(Rating.user_id == user_id).delete()
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"status": "ok"}

@router.get("/users/{user_id}/ratings")
def user_ratings(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
    result = []
    for r in ratings:
        game = db.query(Game).filter(Game.id == r.game_id).first()
        result.append({
            "game_id": r.game_id,
            "game_name": game.name if game else "未知",
            "score": r.score,
            "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else ""
        })
    return {"ratings": result}

# ========== 同步监控 ==========

@router.get("/sync/status")
def sync_status(admin: User = Depends(require_admin)):
    running = _scheduler.running if _scheduler else False
    jobs = _scheduler.get_jobs() if _scheduler else []
    next_sync = ""
    for j in jobs:
        if j.name == "sync_steam_data" and j.next_run_time:
            next_sync = j.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            break
    return {
        "running": running,
        "next_scheduled": next_sync,
        "jobs_count": len(jobs)
    }

@router.post("/sync/trigger")
def trigger_sync(admin: User = Depends(require_admin)):
    from threading import Thread
    t = Thread(target=sync_steam_data, daemon=True)
    t.start()
    return {"status": "started", "message": "同步已在后台启动"}

@router.get("/sync/stats")
def sync_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    today = date.today()
    total_games = db.query(func.count(Game.id)).scalar()
    total_ratings = db.query(func.count(Rating.id)).scalar()
    today_ranked = db.query(func.count(DailyTopSeller.id)).filter(DailyTopSeller.date == today).scalar()

    # 最近每天入库的游戏数
    daily = db.query(
        DailyTopSeller.date,
        func.count(DailyTopSeller.id).label("cnt")
    ).group_by(DailyTopSeller.date).order_by(DailyTopSeller.date.desc()).limit(7).all()

    incomplete = db.query(func.count(Game.id)).filter(
        (Game.screenshots == "[]") | (Game.screenshots.is_(None))
    ).scalar()

    return {
        "total_games": total_games,
        "total_ratings": total_ratings,
        "today_ranked": today_ranked,
        "incomplete_games": incomplete,
        "daily_history": [{"date": str(d), "count": c} for d, c in daily]
    }

@router.get("/sync/game/{game_id}")
def game_sync_info(
    game_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(404, "游戏不存在")
    try:
        screenshots = json.loads(game.screenshots or "[]")
    except:
        screenshots = []
    return {
        "id": game.id,
        "name": game.name,
        "name_cn": game.name_cn or "",
        "steam_app_id": game.steam_app_id,
        "has_description": bool(game.description and len(game.description) > 50),
        "screenshots_count": len(screenshots),
        "tags_count": len(game.tags),
        "updated_at": game.updated_at.strftime("%Y-%m-%d %H:%M") if game.updated_at else "",
        "reviews_synced_at": game.reviews_synced_at.strftime("%Y-%m-%d %H:%M") if game.reviews_synced_at else "未同步",
    }

# ========== 日志查看 ==========

@router.get("/logs")
def view_logs(
    target_date: str = Query("", description="日期 YYYY-MM-DD，空=今天"),
    level: str = Query("ALL"),
    lines: int = Query(100, ge=10, le=500),
    admin: User = Depends(require_admin),
):
    if target_date:
        log_file = os.path.join(LOG_DIR, f"gameplan.log.{target_date}")
    else:
        log_file = os.path.join(LOG_DIR, "gameplan.log")

    # 如果指定日期的日志不存在，尝试查主日志
    if not os.path.isfile(log_file):
        log_file = os.path.join(LOG_DIR, "gameplan.log")

    raw_lines = []
    if os.path.isfile(log_file):
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = [line.rstrip("\n") for line in f.readlines()]

    # 级别过滤
    if level != "ALL":
        raw_lines = [l for l in raw_lines if f"[{level}]" in l]

    total = len(raw_lines)
    recent = raw_lines[-lines:]

    return {"lines": recent, "total": total, "file": os.path.basename(log_file)}
```

- [ ] **Step 2: 在 main.py 中注册 admin router**

在 `backend/main.py` 的 router 注册区域（`app.include_router(ratings_router, ...)` 之后）添加：

```python
from admin import router as admin_router
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
```

- [ ] **Step 3: 验证后端启动 + API 测试**

```bash
pkill -f "uvicorn main:app" 2>/dev/null
cd /chenghao/claudeProject/GamePlan/backend && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
sleep 3
# 登录管理员
curl -s -c /tmp/admin_cookie.txt -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" -d '{"username":"chengixr","password":"yourpass"}'
# 测试 admin 接口
curl -s -b /tmp/admin_cookie.txt http://127.0.0.1:8000/api/admin/users | python3 -m json.tool | head -10
curl -s -b /tmp/admin_cookie.txt http://127.0.0.1:8000/api/admin/sync/status
curl -s -b /tmp/admin_cookie.txt "http://127.0.0.1:8000/api/admin/logs?lines=20"
```

- [ ] **Step 4: 提交**

```bash
git add backend/admin.py backend/main.py
git commit -m "feat: 后端管理API - 用户管理/同步监控/日志查看 9个端点"
```

---

### Task 4: 前端 API + Auth Store + Router

**Files:** Modify `frontend/src/api/index.js`, `frontend/src/stores/auth.js`, `frontend/src/router/index.js`

- [ ] **Step 1: api/index.js 添加 admin 方法**

在 `frontend/src/api/index.js` 的 `api` 对象末尾（`}` 之前）添加：

```js
  // admin
  adminUsers: (search = '', page = 1, pageSize = 20) =>
    request(`/admin/users?search=${encodeURIComponent(search)}&page=${page}&page_size=${pageSize}`),
  adminUserStatus: (userId, isActive) =>
    request(`/admin/users/${userId}/status`, { method: 'PUT', body: JSON.stringify({ is_active: isActive }) }),
  adminDeleteUser: (userId) =>
    request(`/admin/users/${userId}`, { method: 'DELETE' }),
  adminUserRatings: (userId) =>
    request(`/admin/users/${userId}/ratings`),
  adminSyncStatus: () => request('/admin/sync/status'),
  adminSyncTrigger: () => request('/admin/sync/trigger', { method: 'POST' }),
  adminSyncStats: () => request('/admin/sync/stats'),
  adminSyncGame: (gameId) => request(`/admin/sync/game/${gameId}`),
  adminLogs: (date = '', level = 'ALL', lines = 100) =>
    request(`/admin/logs?target_date=${date}&level=${level}&lines=${lines}`),
```

- [ ] **Step 2: router/index.js 添加 /admin 路由**

在 routes 数组末尾（`]` 之前）添加：

```js
  { path: '/admin', name: 'Admin', component: () => import('../views/AdminView.vue'), meta: { requiresAdmin: true } },
```

在 `router.beforeEach` 中，`to.meta.requiresAuth` 判断之后添加：

```js
  if (to.meta.requiresAdmin && !auth.user?.is_admin) {
    next('/hot')
  } else if (to.meta.requiresAuth && !auth.user) {
    next('/login')
  } else {
    next()
  }
```

替换原来的：

```js
  if (to.meta.requiresAuth && !auth.user) {
    next('/login')
  } else {
    next()
  }
```

完整 router.beforeEach：

```js
router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()
  if (!auth.user) {
    try { await auth.checkAuth() } catch {}
  }
  if (to.meta.requiresAdmin && !auth.user?.is_admin) {
    next('/hot')
  } else if (to.meta.requiresAuth && !auth.user) {
    next('/login')
  } else {
    next()
  }
})
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/api/index.js frontend/src/router/index.js
git commit -m "feat: 前端admin路由守卫+API方法"
```

---

### Task 5: NavBar 添加管理入口

**Files:** Modify `frontend/src/components/NavBar.vue`

- [ ] **Step 1: 在 NavBar 中添加管理链接**

在热销榜链接之后、推荐链接之前：

```vue
      <router-link to="/hot" class="nav-link">热销榜</router-link>
      <router-link v-if="auth.user?.is_admin" to="/admin" class="nav-link nav-link--admin">管理</router-link>
      <router-link v-if="auth.user" to="/recommend" class="nav-link">推荐</router-link>
```

- [ ] **Step 2: 添加管理链接特殊样式**

在 `<style scoped>` 中 `.nav-link--accent` 样式之后：

```css
.nav-link--admin { color: var(--neon-amber) !important; }
.nav-link--admin:hover { color: var(--neon-amber) !important; text-shadow: 0 0 8px rgba(255,184,0,0.3); }
```

- [ ] **Step 3: 提交**

```bash
git add frontend/src/components/NavBar.vue
git commit -m "feat: NavBar添加管理入口 - is_admin用户可见"
```

---

### Task 6: AdminView.vue 主容器

**Files:** Create `frontend/src/views/AdminView.vue`

- [ ] **Step 1: 创建 AdminView.vue**

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
  </div>
</template>

<script setup>
import { ref } from 'vue'
import AdminUsers from '../components/AdminUsers.vue'
import AdminSync from '../components/AdminSync.vue'
import AdminLogs from '../components/AdminLogs.vue'

const activeTab = ref('users')
const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'sync', label: '同步监控' },
  { key: 'logs', label: '日志查看' },
]
</script>

<style scoped>
.admin { max-width: 1100px; margin: 0 auto; padding: 24px; }

.admin-title {
  font-family: var(--font-display);
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 4px;
  margin-bottom: 28px;
  color: var(--text-primary);
}

.admin-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 28px;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  padding-bottom: 0;
}

.admin-tab {
  background: transparent;
  border: none;
  padding: 10px 22px;
  font-family: var(--font-body);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1px;
  transition: all 0.2s;
}
.admin-tab:hover { color: var(--text-primary); }
.admin-tab.active {
  color: var(--neon-cyan);
  border-bottom-color: var(--neon-cyan);
}
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/views/AdminView.vue
git commit -m "feat: AdminView主容器+Tab切换"
```

---

### Task 7: AdminUsers.vue 用户管理 Tab

**Files:** Create `frontend/src/components/AdminUsers.vue`

- [ ] **Step 1: 创建 AdminUsers.vue**

```vue
<template>
  <div class="au-wrap">
    <div class="au-toolbar">
      <input v-model="search" class="au-search" placeholder="搜索用户名或昵称..." @keyup.enter="loadUsers" />
      <button class="au-btn" @click="loadUsers">搜索</button>
    </div>

    <div class="au-table-wrap" v-if="!loading">
      <table class="au-table" v-if="users.length">
        <thead>
          <tr>
            <th>ID</th><th>用户名</th><th>昵称</th><th>评分</th><th>注册时间</th><th>状态</th><th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id" :class="{ inactive: !u.is_active }">
            <td>{{ u.id }}</td>
            <td>{{ u.username }}</td>
            <td>{{ u.nickname }}</td>
            <td>{{ u.rating_count }}</td>
            <td>{{ u.created_at }}</td>
            <td><span class="au-status" :class="{ off: !u.is_active }">{{ u.is_active ? '启用' : '禁用' }}</span></td>
            <td class="au-actions">
              <button class="au-action-btn" @click="toggleStatus(u)">{{ u.is_active ? '禁用' : '启用' }}</button>
              <button class="au-action-btn" @click="viewRatings(u)">评分</button>
              <button class="au-action-btn danger" @click="deleteUser(u)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
      <div class="au-empty" v-else>暂无用户数据</div>
    </div>
    <div class="au-loading" v-else>加载中...</div>

    <!-- 分页 -->
    <div class="au-pager" v-if="total > pageSize">
      <button :disabled="page <= 1" @click="page--; loadUsers()">上一页</button>
      <span>{{ page }} / {{ Math.ceil(total / pageSize) }}</span>
      <button :disabled="page >= Math.ceil(total / pageSize)" @click="page++; loadUsers()">下一页</button>
    </div>

    <!-- 评分弹窗 -->
    <div class="au-modal-overlay" v-if="ratingUser" @click.self="ratingUser = null">
      <div class="au-modal">
        <h3>{{ ratingUser.username }} 的评分记录</h3>
        <div class="au-ratings-list" v-if="ratings.length">
          <div v-for="r in ratings" :key="r.game_id" class="au-rating-row">
            <span>{{ r.game_name }}</span>
            <span class="au-stars">{{ '★'.repeat(r.score) }}{{ '☆'.repeat(5 - r.score) }}</span>
            <span class="au-rating-date">{{ r.created_at }}</span>
          </div>
        </div>
        <div v-else>暂无评分</div>
        <button class="au-btn" @click="ratingUser = null">关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'

const search = ref('')
const users = ref([])
const loading = ref(false)
const page = ref(1)
const pageSize = 20
const total = ref(0)

const ratingUser = ref(null)
const ratings = ref([])

async function loadUsers() {
  loading.value = true
  try {
    const res = await api.adminUsers(search.value, page.value, pageSize)
    users.value = res.items
    total.value = res.total
  } catch { users.value = [] }
  finally { loading.value = false }
}

async function toggleStatus(u) {
  const newStatus = !u.is_active
  try {
    await api.adminUserStatus(u.id, newStatus)
    u.is_active = newStatus
  } catch (e) { alert(e.message) }
}

async function deleteUser(u) {
  if (!confirm(`确定删除用户 "${u.username}" 吗？该操作不可撤销。`)) return
  try {
    await api.adminDeleteUser(u.id)
    loadUsers()
  } catch (e) { alert(e.message) }
}

async function viewRatings(u) {
  ratingUser.value = u
  try {
    const res = await api.adminUserRatings(u.id)
    ratings.value = res.ratings || []
  } catch { ratings.value = [] }
}

onMounted(() => loadUsers())
</script>

<style scoped>
.au-wrap { color: var(--text-primary); }
.au-toolbar { display: flex; gap: 10px; margin-bottom: 20px; }
.au-search {
  flex: 1; max-width: 320px;
  padding: 8px 14px;
  background: var(--surface);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}
.au-search:focus { border-color: var(--neon-cyan); }
.au-btn {
  padding: 8px 18px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 6px;
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.15s;
}
.au-btn:hover { border-color: var(--neon-cyan); color: var(--neon-cyan); }

.au-table-wrap { overflow-x: auto; }
.au-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.au-table th {
  text-align: left; padding: 10px 12px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  color: var(--text-muted); font-weight: 500; font-size: 12px;
  letter-spacing: 1px; text-transform: uppercase;
}
.au-table td { padding: 10px 12px; border-bottom: 1px solid rgba(255,255,255,0.03); }
.au-table tr.inactive td { opacity: 0.45; }
.au-status { font-size: 12px; padding: 2px 8px; border-radius: 3px; background: rgba(16,185,129,0.12); color: #10b981; }
.au-status.off { background: rgba(255,45,120,0.1); color: var(--neon-magenta); }
.au-actions { display: flex; gap: 6px; }
.au-action-btn {
  padding: 3px 10px; font-size: 12px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px; color: var(--text-secondary);
  cursor: pointer; transition: all 0.15s;
}
.au-action-btn:hover { color: var(--neon-cyan); border-color: rgba(0,229,255,0.2); }
.au-action-btn.danger:hover { color: var(--neon-magenta); border-color: rgba(255,45,120,0.2); }

.au-pager { display: flex; align-items: center; gap: 14px; margin-top: 20px; justify-content: center; }
.au-pager button {
  padding: 6px 16px;
  background: var(--surface-raised);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 4px; color: var(--text-secondary);
  font-size: 13px; cursor: pointer;
}
.au-pager button:hover:not(:disabled) { color: var(--neon-cyan); border-color: rgba(0,229,255,0.2); }
.au-pager button:disabled { opacity: 0.3; cursor: default; }

.au-modal-overlay {
  position: fixed; inset: 0; z-index: 500;
  background: rgba(0,0,0,0.6);
  display: flex; align-items: center; justify-content: center;
}
.au-modal {
  background: var(--surface);
  border: 1px solid rgba(0,229,255,0.12);
  border-radius: 12px;
  padding: 28px;
  min-width: 420px;
  max-width: 560px;
  max-height: 70vh;
  overflow-y: auto;
}
.au-modal h3 { margin-bottom: 16px; font-size: 16px; }
.au-ratings-list { display: flex; flex-direction: column; gap: 8px; margin-bottom: 16px; }
.au-rating-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.04); }
.au-stars { color: var(--neon-amber); font-size: 13px; }
.au-rating-date { font-size: 12px; color: var(--text-muted); }
.au-empty, .au-loading { text-align: center; padding: 40px; color: var(--text-muted); }
</style>
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/AdminUsers.vue
git commit -m "feat: AdminUsers - 用户列表/搜索/禁用/删除/评分查看"
```

---

### Task 8: AdminSync.vue 同步监控 Tab

**Files:** Create `frontend/src/components/AdminSync.vue`

- [ ] **Step 1: 创建 AdminSync.vue**

```vue
<template>
  <div class="as-wrap">
    <!-- 状态卡片 -->
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

    <!-- 操作 -->
    <div class="as-actions">
      <button class="as-btn sync-btn" @click="triggerSync" :disabled="syncing">
        {{ syncing ? '同步中...' : '手动同步' }}
      </button>
      <span class="as-msg" v-if="syncMsg">{{ syncMsg }}</span>
    </div>

    <!-- 每日统计 -->
    <div class="as-section" v-if="stats.daily_history?.length">
      <h3>每日入库统计</h3>
      <table class="as-table">
        <thead><tr><th>日期</th><th>入库游戏数</th></tr></thead>
        <tbody>
          <tr v-for="d in stats.daily_history" :key="d.date">
            <td>{{ d.date }}</td><td>{{ d.count }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 游戏查询 -->
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
  try {
    gameInfo.value = await api.adminSyncGame(parseInt(gameQuery.value))
  } catch { gameInfo.value = null }
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
.as-btn, .sync-btn {
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/AdminSync.vue
git commit -m "feat: AdminSync - 同步状态/统计/手动触发/游戏查询"
```

---

### Task 9: AdminLogs.vue 日志查看 Tab

**Files:** Create `frontend/src/components/AdminLogs.vue`

- [ ] **Step 1: 创建 AdminLogs.vue**

```vue
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
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
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
    // 滚动到底部
    setTimeout(() => {
      if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight
    }, 50)
  } catch { logs.value = '(加载失败)' }
  finally { loading.value = false }
}

watch(autoRefresh, (v) => {
  if (timer) { clearInterval(timer); timer = null }
  if (v) {
    timer = setInterval(loadLogs, 5000)
  }
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
```

- [ ] **Step 2: 提交**

```bash
git add frontend/src/components/AdminLogs.vue
git commit -m "feat: AdminLogs - 日志查看/日期选择/级别过滤/自动刷新"
```

---

### Task 10: 构建并功能验证

- [ ] **Step 1: 构建前端**

```bash
cd /chenghao/claudeProject/GamePlan/frontend && npm run build
```

预期：构建成功

- [ ] **Step 2: 重启后端**

```bash
pkill -f "uvicorn main:app" 2>/dev/null
cd /chenghao/claudeProject/GamePlan/backend && nohup uvicorn main:app --host 0.0.0.0 --port 8000 > /tmp/backend.log 2>&1 &
sleep 3 && curl -s http://127.0.0.1:8000/api/health
```

- [ ] **Step 3: 验证清单**

1. 管理员用户登录 → 导航栏出现"管理"链接（琥珀色）
2. 普通用户登录 → 导航栏不出现"管理"链接
3. 点击管理 → 进入 `/admin`，三个 Tab 正确切换
4. 用户管理：搜索、禁用/启用、删除（自己不可删）、查看评分弹窗
5. 同步监控：状态卡片、统计表、手动同步按钮
6. 日志查看：日期选择、级别过滤、自动刷新
7. 非管理员直接访问 `/admin` → 重定向到 `/hot`

- [ ] **Step 4: 提交**

```bash
git add .
git commit -m "feat: 管理后台页面完整实现 - 用户管理+同步监控+日志查看"
```
