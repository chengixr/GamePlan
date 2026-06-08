# 游戏收藏功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户可收藏/取消收藏游戏，在导航栏"收藏"页面查看收藏列表

**Architecture:** 新增 `favorites` 表 + `/api/favorites` 路由 + `FavoriteButton` 组件。按钮独立管理收藏状态（mounted 时查询），不侵入现有 GameResponse 结构。

**Tech Stack:** FastAPI + SQLAlchemy + Vue 3 + Pinia

---

### Task 1: 数据库 — 新增 Favorite 模型

**Files:**
- Modify: `backend/database.py`

- [ ] **Step 1: 在 Game 模型之后添加 Favorite 模型**

```python
class Favorite(Base):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "game_id"),)
```

放在 `GameEmbedding` 类之前（line 86 附近），与其他模型风格一致。

- [ ] **Step 2: 验证模型可导入**

```bash
cd backend && python3 -c "from database import Favorite; print('Favorite imported OK, table:', Favorite.__tablename__)"
```

Expected: `Favorite imported OK, table: favorites`

- [ ] **Step 3: 在现有数据库中创建表**

```bash
cd backend && python3 -c "
from database import engine, Base
from models import Favorite  # trigger registration
Base.metadata.create_all(bind=engine)
print('Table created')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/database.py && git commit -m "feat: 新增 Favorite 模型（user_id+game_id 联合唯一）"
```

---

### Task 2: 后端 API — favorites 路由

**Files:**
- Create: `backend/favorites.py`
- Modify: `backend/main.py`

- [ ] **Step 5: 创建 favorites.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from database import SessionLocal, Game, Favorite
from models import GameResponse, PaginatedResponse
from auth import get_current_user, get_db

router = APIRouter()


@router.post("/{game_id}")
def toggle_favorite(
    game_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    game = db.query(Game).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    fav = db.query(Favorite).filter(
        Favorite.user_id == current_user.id,
        Favorite.game_id == game_id,
    ).first()

    if fav:
        db.delete(fav)
        db.commit()
        return {"favorited": False}
    else:
        db.add(Favorite(user_id=current_user.id, game_id=game_id))
        db.commit()
        return {"favorited": True}


@router.get("/ids")
def favorite_ids(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """返回当前用户已收藏的 game_id 列表"""
    ids = [row[0] for row in db.query(Favorite.game_id).filter(
        Favorite.user_id == current_user.id
    ).all()]
    return {"ids": ids}


@router.get("", response_model=PaginatedResponse)
def list_favorites(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    total = db.query(Favorite).filter(
        Favorite.user_id == current_user.id
    ).count()

    favs = db.query(Favorite).filter(
        Favorite.user_id == current_user.id
    ).order_by(Favorite.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    game_ids = [f.game_id for f in favs]
    games_map = {}
    if game_ids:
        games = db.query(Game).options(joinedload(Game.tags)).filter(
            Game.id.in_(game_ids)
        ).all()
        games_map = {g.id: g for g in games}

    items = []
    for f in favs:
        g = games_map.get(f.game_id)
        if g:
            fallback = ""
            try:
                import json
                ss = json.loads(g.screenshots or "[]")
                for s in ss:
                    if s.startswith("/static/"):
                        fallback = s
                        break
            except: pass
            items.append(GameResponse(
                id=g.id, steam_app_id=g.steam_app_id,
                name=g.name, name_cn=g.name_cn or "",
                description=g.description or "",
                image_url=g.image_url or "",
                fallback_image=fallback,
                price=g.price or "",
                tags=[t.name for t in g.tags],
            ))

    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)
```

- [ ] **Step 6: 在 main.py 注册路由**

在 `main.py` 中（位于 ratings 路由注册之后，admin 路由之前）：

```python
from favorites import router as favorites_router
app.include_router(favorites_router, prefix="/api/favorites", tags=["favorites"])
```

所在位置：line 71 附近 `app.include_router(ratings_router, ...)` 之后。

- [ ] **Step 7: 测试 API**

```bash
# 重启服务
fuser -k 8000/tcp 2>/dev/null; sleep 1; cd /chenghao/claudeProject/GamePlan && ./start.sh prod

# 测试（需要先登录获取 cookie）
# 收藏游戏
curl -X POST http://localhost:8000/api/favorites/1 -c /tmp/cookies.txt -b /tmp/cookies.txt
# 获取收藏 ID 列表
curl http://localhost:8000/api/favorites/ids -b /tmp/cookies.txt
# 获取收藏列表
curl "http://localhost:8000/api/favorites?page=1&page_size=10" -b /tmp/cookies.txt
```

- [ ] **Step 8: Commit**

```bash
git add backend/favorites.py backend/main.py && git commit -m "feat: 收藏 API（toggle/ids/list）"
```

---

### Task 3: 前端 API — 收藏接口

**Files:**
- Modify: `frontend/src/api/index.js`

- [ ] **Step 9: 在 api 对象中添加收藏方法**

在 `adminSchedulerTrigger` 行之前添加：

```javascript
  toggleFavorite: (gameId) => request(`/favorites/${gameId}`, { method: 'POST' }),
  favoriteIds: () => request('/favorites/ids'),
  favorites: (page = 1, pageSize = 20) => request(`/favorites?page=${page}&page_size=${pageSize}`),
```

- [ ] **Step 10: Commit**

```bash
git add frontend/src/api/index.js && git commit -m "feat: 前端 API 新增收藏接口"
```

---

### Task 4: 前端组件 — FavoriteButton

**Files:**
- Create: `frontend/src/components/FavoriteButton.vue`

- [ ] **Step 11: 创建 FavoriteButton.vue**

```vue
<template>
  <button class="fav-btn" :class="{ favorited }" @click.prevent.stop="toggle" :title="favorited ? '取消收藏' : '收藏'">
    <svg viewBox="0 0 24 24" class="fav-icon">
      <path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z"
        :fill="favorited ? '#ff2d78' : 'none'"
        :stroke="favorited ? '#ff2d78' : 'currentColor'"
        stroke-width="1.5" />
    </svg>
  </button>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import { useAuthStore } from '../stores/auth'

const props = defineProps({ gameId: Number })
const auth = useAuthStore()
const favorited = ref(false)
const loading = ref(false)

onMounted(async () => {
  if (!auth.user) return
  try {
    const data = await api.favoriteIds()
    favorited.value = data.ids.includes(props.gameId)
  } catch {}
})

async function toggle() {
  if (!auth.user || loading.value) return
  loading.value = true
  const prev = favorited.value
  favorited.value = !prev
  try {
    const data = await api.toggleFavorite(props.gameId)
    favorited.value = data.favorited
  } catch {
    favorited.value = prev
  }
  loading.value = false
}
</script>

<style scoped>
.fav-btn {
  position: absolute;
  top: 8px; right: 8px;
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: rgba(6,6,11,0.8);
  border: 1px solid rgba(255,255,255,0.08);
  border-radius: 6px;
  cursor: pointer;
  backdrop-filter: blur(6px);
  transition: border-color 0.2s, background 0.2s;
  z-index: 5;
}
.fav-btn:hover { border-color: rgba(255,45,120,0.4); background: rgba(255,45,120,0.1); }
.fav-btn.favorited { border-color: rgba(255,45,120,0.3); background: rgba(255,45,120,0.08); }
.fav-icon { width: 18px; height: 18px; color: var(--text-muted); transition: color 0.2s; }
.fav-btn:hover .fav-icon { color: var(--neon-magenta); }
.fav-btn.favorited .fav-icon { color: #ff2d78; }
</style>
```

- [ ] **Step 12: Commit**

```bash
git add frontend/src/components/FavoriteButton.vue && git commit -m "feat: FavoriteButton 组件（心形切换按钮）"
```

---

### Task 5: 前端页面 — FavoritesView

**Files:**
- Create: `frontend/src/views/FavoritesView.vue`

- [ ] **Step 13: 创建 FavoritesView.vue**

```vue
<template>
  <div class="favorites">
    <h2 class="page-title">我的收藏</h2>
    <div v-if="loading && !games.length" class="empty">加载中...</div>
    <div v-else-if="!games.length && !loading" class="empty">
      <p>还没有收藏游戏</p>
      <router-link to="/hot" class="go-hot">去热销榜看看吧</router-link>
    </div>
    <template v-else>
      <GameCard v-for="game in games" :key="game.id" :game="game" :show-rating="true" />
      <div ref="sentinel" class="sentinel"></div>
      <div v-if="loadingMore" class="loading-more">加载更多...</div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { api } from '../api'
import GameCard from '../components/GameCard.vue'

const games = ref([])
const page = ref(1)
const total = ref(0)
const loading = ref(true)
const loadingMore = ref(false)
const sentinel = ref(null)
let observer = null

async function loadPage(p) {
  const data = await api.favorites(p, 20)
  if (p === 1) {
    games.value = data.items
  } else {
    games.value.push(...data.items)
  }
  total.value = data.total
}

onMounted(async () => {
  try { await loadPage(1) } catch {}
  loading.value = false

  observer = new IntersectionObserver(([entry]) => {
    if (entry.isIntersecting && games.value.length < total.value && !loadingMore.value) {
      loadingMore.value = true
      page.value++
      loadPage(page.value).finally(() => { loadingMore.value = false })
    }
  }, { rootMargin: '200px' })
  if (sentinel.value) observer.observe(sentinel.value)
})

onBeforeUnmount(() => { if (observer) observer.disconnect() })
</script>

<style scoped>
.favorites { max-width: 900px; margin: 0 auto; padding: 24px 16px; }
.page-title {
  font-family: var(--font-display);
  font-size: 24px; font-weight: 700; color: var(--text-primary);
  margin-bottom: 24px; letter-spacing: 1px;
}
.empty { text-align: center; padding: 60px 0; color: var(--text-muted); font-size: 16px; }
.go-hot {
  display: inline-block; margin-top: 12px;
  color: var(--neon-cyan); text-decoration: none; font-weight: 500;
}
.go-hot:hover { text-decoration: underline; }
.sentinel { height: 1px; }
.loading-more { text-align: center; padding: 20px; color: var(--text-muted); font-size: 14px; }
</style>
```

- [ ] **Step 14: Commit**

```bash
git add frontend/src/views/FavoritesView.vue && git commit -m "feat: FavoritesView 收藏列表页面"
```

---

### Task 6: 路由和导航集成

**Files:**
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/NavBar.vue`
- Modify: `frontend/src/components/GameCard.vue`
- Modify: `frontend/src/views/GameDetail.vue`

- [ ] **Step 15: 添加 /favorites 路由**

在 `router/index.js` 的 `/recommend` 路由之后添加：

```javascript
  { path: '/favorites', name: 'Favorites', component: () => import('../views/FavoritesView.vue'), meta: { requiresAuth: true } },
```

- [ ] **Step 16: NavBar 添加"收藏"菜单**

在 `NavBar.vue` 中，`<router-link to="/recommend">` 之后添加：

```html
<router-link v-if="auth.user" to="/favorites" class="nav-link">收藏</router-link>
```

- [ ] **Step 17: GameCard 添加 FavoriteButton**

GameCard 需要两处修改：

**模板 —** 在 `<div class="card-image-wrap">` 内部，`<div class="card-rank">` 后面添加：

```html
<FavoriteButton v-if="auth.user" :game-id="game.id" />
```

**脚本 —** import FavoriteButton 和 useAuthStore：

```javascript
import FavoriteButton from './FavoriteButton.vue'
import { useAuthStore } from '../stores/auth'
const auth = useAuthStore()
```

- [ ] **Step 18: GameDetail 添加 FavoriteButton**

**模板 —** 在 `<div class="hero-left">` 内部，`<h1 class="hero-title">` 前面添加：

```html
<FavoriteButton v-if="auth.user" :game-id="game.id" class="fav-detail" />
```

**脚本 —** import FavoriteButton：

```javascript
import FavoriteButton from '../components/FavoriteButton.vue'
```

**样式 —** 添加 scoped style 让详情页按钮不使用绝对定位：

```css
.fav-detail :deep(.fav-btn) {
  position: static;
  margin-bottom: 8px;
}
```

- [ ] **Step 19: 测试前端**

```bash
cd frontend && npm run build
```

确认构建无错误。

- [ ] **Step 20: Commit**

```bash
git add frontend/src/router/index.js frontend/src/components/NavBar.vue frontend/src/components/GameCard.vue frontend/src/views/GameDetail.vue && git commit -m "feat: 集成收藏按钮到卡片、详情页和导航栏"
```
