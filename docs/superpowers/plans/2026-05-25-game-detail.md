# 游戏详情页 - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 新增游戏详情页，展示游戏截图、Steam 评价、相似游戏推荐，支持评分。游戏卡片可点击进入详情页。

**Architecture:** Game 表新增截图/评价 JSON 字段，Steam 同步每日更新。详情 API 实时计算相似游戏。前端新建 GameDetail 页面，GameCard 包裹 router-link。

**Tech Stack:** Vue 3 + FastAPI + SQLite

---

### Task 1: 数据库新增字段

**Files:**
- Modify: `backend/database.py:27-39`

- [ ] **Step 1: 添加 screenshots、review_summary、reviews_synced_at 列到 Game 模型**

```python
class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_app_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(256), nullable=False)
    name_cn = Column(String(256), default="")
    description = Column(Text, default="")
    image_url = Column(String(512), default="")
    price = Column(String(32), default="")
    release_date = Column(String(32), default="")
    screenshots = Column(Text, default="[]")
    review_summary = Column(Text, default="{}")
    reviews_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    tags = relationship("Tag", secondary=game_tag_assoc, back_populates="games")
```

- [ ] **Step 2: 运行 ALTER TABLE 添加列**

```bash
sqlite3 /chenghao/claudeProject/GamePlan/backend/gameplan.db "ALTER TABLE games ADD COLUMN screenshots TEXT DEFAULT '[]';"
sqlite3 /chenghao/claudeProject/GamePlan/backend/gameplan.db "ALTER TABLE games ADD COLUMN review_summary TEXT DEFAULT '{}';"
sqlite3 /chenghao/claudeProject/GamePlan/backend/gameplan.db "ALTER TABLE games ADD COLUMN reviews_synced_at DATETIME;"
```

- [ ] **Step 3: 验证**

```bash
sqlite3 /chenghao/claudeProject/GamePlan/backend/gameplan.db ".schema games"
```

输出应包含 `screenshots TEXT DEFAULT '[]'`, `review_summary TEXT DEFAULT '{}'`, `reviews_synced_at DATETIME`

---

### Task 2: Steam 同步截图与评价

**Files:**
- Modify: `backend/steam_sync.py`

- [ ] **Step 1: 更新 `_try_fetch_details` 返回截图和评价数据**

```python
def _try_fetch_details(appid: int) -> dict | None:
    try:
        data = _fetch_json(f"appdetails?appids={appid}&cc=cn&l=schinese", timeout=20)
        gd = data.get(str(appid), {}).get("data", {})
        if not gd.get("name"):
            return None
        tags = [translate_tag(g.get("description", "")) for g in gd.get("genres", [])]
        tags += [translate_tag(c.get("description", "")) for c in gd.get("categories", [])]

        # 截图
        screenshots = []
        for s in gd.get("screenshots", [])[:10]:
            url = s.get("path_full", "")
            if url:
                screenshots.append(url)

        # 评价
        recs = gd.get("recommendations", {})
        review_positive = recs.get("total", 0)
        total_reviews = recs.get("total_reviews", 0) or (review_positive * 100 // max(1, 80))
        review_summary = json.dumps({"positive": review_positive, "total": total_reviews})

        return {
            "name_cn": gd.get("name", ""),
            "description": gd.get("short_description", ""),
            "release_date": gd.get("release_date", {}).get("date", ""),
            "tags": tags,
            "screenshots": json.dumps(screenshots),
            "review_summary": review_summary,
        }
    except Exception:
        return None
```

- [ ] **Step 2: 更新 `sync_steam_data` 中新建 game 的部分，存储截图和评价**

将 Game 构造改为：
```python
game = Game(
    steam_app_id=appid,
    name=item["name"],
    name_cn=details.get("name_cn", "") if details else "",
    description=details.get("description", "") if details else "",
    image_url=local_img if downloaded else cdn_img,
    price=item["price"],
    release_date=details.get("release_date", "") if details else "",
    screenshots=details.get("screenshots", "[]") if details else "[]",
    review_summary=details.get("review_summary", "{}") if details else "{}",
    reviews_synced_at=datetime.now(timezone.utc) if details else None,
)
```

- [ ] **Step 3: 更新已有游戏的截图/评价补充逻辑**

在已有游戏的更新路径中，增加：
```python
# 补充截图和评价（24小时内跳过）
if game.reviews_synced_at is None or \
   (datetime.now(timezone.utc) - game.reviews_synced_at.replace(tzinfo=timezone.utc)) > timedelta(hours=24):
    _details = _try_fetch_details(appid)
    if _details:
        game.screenshots = _details.get("screenshots", "[]")
        game.review_summary = _details.get("review_summary", "{}")
        game.reviews_synced_at = datetime.now(timezone.utc)
```

- [ ] **Step 4: 验证**

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from steam_sync import _try_fetch_details
d = _try_fetch_details(730)
print(f'screenshots: {len(json.loads(d[\"screenshots\"]))}' if d else 'FAIL')
print(f'reviews: {d[\"review_summary\"]}' if d else '')
"
```

---

### Task 3: 相似游戏算法

**Files:**
- Modify: `backend/recommender.py`

- [ ] **Step 1: 新增 `get_similar_games` 函数**

```python
def get_similar_games(db: Session, game_id: int, limit: int = 6) -> list[int]:
    """基于标签 + 协同过滤返回相似游戏"""
    target_game = db.query(Game).filter(Game.id == game_id).first()
    if not target_game:
        return []

    target_tags = {t.name for t in target_game.tags}
    all_games = db.query(Game).filter(Game.id != game_id).all()

    # 标签 Jaccard 相似度
    tag_scores = {}
    for g in all_games:
        g_tags = {t.name for t in g.tags}
        if not target_tags or not g_tags:
            tag_scores[g.id] = 0.0
        else:
            inter = len(target_tags & g_tags)
            union = len(target_tags | g_tags)
            tag_scores[g.id] = inter / union if union > 0 else 0.0

    # 协同过滤：找到评分过当前游戏的用户，看他们还喜欢什么
    all_ratings = db.query(Rating).all()
    user_scores = {}
    for r in all_ratings:
        user_scores.setdefault(r.user_id, {})[r.game_id] = r.score

    cf_scores = {}
    for uid, scores in user_scores.items():
        if game_id in scores and scores[game_id] >= 4:
            # 该用户喜欢当前游戏，其高分游戏获得加分
            for gid, s in scores.items():
                if s >= 4 and gid != game_id:
                    cf_scores[gid] = cf_scores.get(gid, 0) + 1

    # 归一化协同分数
    max_cf = max(cf_scores.values()) if cf_scores else 1
    for gid in cf_scores:
        cf_scores[gid] = cf_scores[gid] / max_cf

    # 混合
    final = {}
    for g in all_games:
        final[g.id] = tag_scores.get(g.id, 0) * 0.6 + cf_scores.get(g.id, 0) * 0.4

    sorted_games = sorted(final.items(), key=lambda x: x[1], reverse=True)
    return [gid for gid, _ in sorted_games[:limit]]
```

---

### Task 4: 游戏详情 API

**Files:**
- Modify: `backend/games.py`

- [ ] **Step 1: 更新 `/game/{game_id}` 端点**

将现有 `game_detail` 替换为：

```python
@router.get("/{game_id}")
def game_detail(game_id: int, db: Session = Depends(get_db),
                request: Request = None):
    game = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    # 解析截图和评价
    screenshots = []
    try: screenshots = json.loads(game.screenshots or "[]")
    except: pass
    review_data = {}
    try: review_data = json.loads(game.review_summary or "{}")
    except: pass

    # 相似游戏
    from recommender import get_similar_games
    similar_ids = get_similar_games(db, game_id, limit=6)
    similar = []
    for gid in similar_ids:
        sg = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == gid).first()
        if sg:
            similar.append(GameResponse(
                id=sg.id, steam_app_id=sg.steam_app_id, name=sg.name,
                name_cn=sg.name_cn or "", description=sg.description or "",
                image_url=sg.image_url or "", price=sg.price or "",
                tags=[t.name for t in sg.tags],
            ))

    return {
        "id": game.id, "steam_app_id": game.steam_app_id,
        "name": game.name, "name_cn": game.name_cn or "",
        "description": game.description or "",
        "image_url": game.image_url or "",
        "price": game.price or "",
        "release_date": game.release_date or "",
        "tags": [t.name for t in game.tags],
        "screenshots": screenshots,
        "review_positive": review_data.get("positive", 0),
        "review_total": review_data.get("total", 0),
        "similar_games": similar,
    }
```

- [ ] **Step 2: 添加 json import**

```python
import json
```
在 games.py 顶部导入区。

- [ ] **Step 3: 验证 API**

```bash
curl -s "http://127.0.0.1:8000/api/games/1" | python3 -c "
import json, sys
d = json.load(sys.stdin)
print(f'name: {d[\"name\"]}')
print(f'screenshots: {len(d[\"screenshots\"])}')
print(f'review: {d[\"review_positive\"]}/{d[\"review_total\"]}')
print(f'similar: {len(d[\"similar_games\"])}')
"
```

---

### Task 5: 前端 API + Store

**Files:**
- Modify: `frontend/src/api/index.js`
- Modify: `frontend/src/stores/games.js`

- [ ] **Step 1: 添加 gameDetail API**

```js
gameDetail: (id) => request(`/games/${id}`),
```
添加到 `export const api = { ... }` 中。

- [ ] **Step 2: 添加 store action**

```js
// games store 新增 state
currentGame: null,

// games store 新增 action
async loadGameDetail(id) {
    this.currentGame = await api.gameDetail(id)
},
```

---

### Task 6: GameCard 可点击

**Files:**
- Modify: `frontend/src/components/GameCard.vue`

- [ ] **Step 1: 包裹 router-link**

将根元素 `<div class="game-card">` 改为 `<router-link>`，保留所有内部结构：

```html
<router-link :to="`/game/${game.id}`" class="game-card">
```
关闭标签改为 `</router-link>`。

需要 `import { RouterLink } from 'vue-router'` 或在 setup 中使用（Vue Router 全局注册了 `<router-link>`，直接可用）。

- [ ] **Step 2: 保持 hover 样式**

```css
.game-card {
  text-decoration: none; color: inherit;
  display: flex; ...
}
```

- [ ] **Step 3: 构建验证**

```bash
cd frontend && npm run build
```

---

### Task 7: GameDetail 页面

**Files:**
- Create: `frontend/src/views/GameDetail.vue`

- [ ] **Step 1: 创建页面**

```vue
<template>
  <div class="detail" v-if="game">
    <!-- 返回 -->
    <button class="btn-back" @click="$router.back()">&#8592; 返回</button>

    <!-- 上区：游戏信息 + 截图 -->
    <div class="detail-top">
      <div class="gallery">
        <img :src="currentImg" class="main-img" />
        <div class="thumbs">
          <img v-for="(s, i) in game.screenshots.slice(0, 8)" :key="i"
            :src="s" class="thumb" :class="{ active: i === activeIdx }"
            @click="activeIdx = i" />
        </div>
      </div>
      <div class="info">
        <h1 class="game-name">{{ game.name }}</h1>
        <p class="game-name-cn" v-if="game.name_cn && game.name_cn !== game.name">{{ game.name_cn }}</p>
        <div class="tags"><span v-for="t in game.tags" :key="t" class="tag">{{ t }}</span></div>
        <div class="meta">
          <span class="price">{{ game.price }}</span>
          <span class="date" v-if="game.release_date">{{ game.release_date }}</span>
        </div>
        <p class="desc">{{ game.description }}</p>
        <StarRating v-model="rating" @update:model-value="onRate" />
      </div>
    </div>

    <!-- 中区：评价 -->
    <div class="review-section" v-if="game.review_total > 0">
      <h2>Steam 评价</h2>
      <div class="review-bar-wrap">
        <div class="review-bar"><div class="review-fill" :style="{ width: reviewPct + '%' }"></div></div>
        <span class="review-text">{{ reviewPct }}% 好评 ({{ game.review_total }} 条评测)</span>
      </div>
    </div>

    <!-- 下区：相似游戏 -->
    <div class="similar-section" v-if="game.similar_games?.length">
      <h2>相似游戏</h2>
      <div class="similar-grid">
        <router-link v-for="sg in game.similar_games" :key="sg.id"
          :to="`/game/${sg.id}`" class="similar-card">
          <img :src="sg.image_url" :alt="sg.name" />
          <span class="similar-name">{{ sg.name }}</span>
        </router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import StarRating from '../components/StarRating.vue'
import { useGamesStore } from '../stores/games'

const route = useRoute()
const store = useGamesStore()

const game = computed(() => store.currentGame)
const activeIdx = ref(0)
const currentImg = computed(() => {
  const ss = game.value?.screenshots || []
  return ss[activeIdx.value] || game.value?.image_url || ''
})
const rating = ref(0)

const reviewPct = computed(() => {
  if (!game.value?.review_total) return 0
  return Math.round(game.value.review_positive / game.value.review_total * 100)
})

async function onRate(score) {
  if (game.value) {
    await store.rate(game.value.id, score)
    rating.value = score
  }
}

onMounted(async () => {
  const id = route.params.id
  await store.loadMyRatings()
  await store.loadGameDetail(id)
  rating.value = store.myRatings[parseInt(id)] || 0
})
</script>

<style scoped>
.detail { max-width: 1000px; margin: 0 auto; padding: 24px; }

.btn-back {
  background: var(--surface-raised); border: 1px solid rgba(255,255,255,0.08);
  color: var(--text-secondary); padding: 8px 16px; border-radius: 6px;
  cursor: pointer; font-size: 14px; margin-bottom: 24px;
  transition: color 0.2s;
}
.btn-back:hover { color: var(--neon-cyan); }

.detail-top { display: flex; gap: 28px; margin-bottom: 32px; }
.gallery { flex: 0 0 480px; max-width: 480px; }
.main-img { width: 100%; aspect-ratio: 16/9; object-fit: cover; border-radius: 8px; }
.thumbs { display: flex; gap: 6px; margin-top: 8px; overflow-x: auto; }
.thumb { width: 80px; height: 45px; object-fit: cover; border-radius: 4px; cursor: pointer; opacity: 0.5; transition: opacity 0.15s; border: 2px solid transparent; }
.thumb:hover, .thumb.active { opacity: 1; border-color: var(--neon-cyan); }

.info { flex: 1; }
.game-name { font-size: 22px; font-weight: 700; }
.game-name-cn { font-size: 15px; color: var(--text-secondary); margin-top: 4px; }
.tags { display: flex; flex-wrap: wrap; gap: 5px; margin: 10px 0; }
.tag { padding: 3px 10px; background: var(--surface-raised); border-radius: 3px; font-size: 12px; color: var(--text-secondary); }
.meta { display: flex; gap: 16px; align-items: center; margin: 12px 0; }
.price { font-size: 18px; color: var(--neon-amber); font-weight: 600; }
.date { font-size: 14px; color: var(--text-muted); }
.desc { font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin: 12px 0; }

.review-section, .similar-section { margin-bottom: 32px; padding: 24px; background: var(--surface); border-radius: 10px; border: 1px solid rgba(255,255,255,0.04); }
.review-section h2, .similar-section h2 { font-family: var(--font-display); font-size: 16px; letter-spacing: 2px; margin-bottom: 14px; }
.review-bar-wrap { display: flex; align-items: center; gap: 14px; }
.review-bar { flex: 1; height: 10px; background: var(--surface-raised); border-radius: 5px; overflow: hidden; }
.review-fill { height: 100%; background: var(--neon-cyan); border-radius: 5px; transition: width 0.4s; }
.review-text { font-size: 14px; color: var(--text-secondary); white-space: nowrap; }

.similar-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; }
.similar-card { text-decoration: none; color: inherit; background: var(--surface-raised); border-radius: 8px; overflow: hidden; transition: transform 0.2s; border: 1px solid rgba(255,255,255,0.04); }
.similar-card:hover { transform: translateY(-2px); border-color: var(--border-glow); }
.similar-card img { width: 100%; aspect-ratio: 16/9; object-fit: cover; }
.similar-name { display: block; padding: 8px; font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

@media (max-width: 768px) {
  .detail-top { flex-direction: column; }
  .gallery { flex: none; max-width: 100%; }
  .similar-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
```

---

### Task 8: 路由配置

**Files:**
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: 添加路由**

```js
{ path: '/game/:id', name: 'GameDetail', component: () => import('../views/GameDetail.vue') },
```

---

## 验证

```bash
cd frontend && npm run build    # 构建前端
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 & # 重启后端
curl -s "http://127.0.0.1:8000/api/games/1" | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'screenshots:{len(d.get(\"screenshots\",[]))} review:{d.get(\"review_positive\",0)}/{d.get(\"review_total\",0)} similar:{len(d.get(\"similar_games\",[]))}')"
curl -s "http://127.0.0.1:5173/game/1" -o /dev/null -w "Frontend HTTP %{http_code}"
```
