# 游戏推荐系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建基于 Steam 热销榜的游戏推荐网站 MVP，支持用户注册/登录、对游戏 1-5 星评分、标签+协同过滤混合推荐。

**Architecture:** Vue 3 SPA 前端 + FastAPI 后端 + SQLite。Nginx 代理静态文件和 API。Steam 数据通过 APScheduler 定时同步。Session cookie 认证。

**Tech Stack:** Vue 3 + Vue Router + Pinia | FastAPI + SQLAlchemy + APScheduler | SQLite | Nginx

---

## 文件结构

```
backend/
├── main.py              # FastAPI 应用入口，挂载路由，配置 CORS/middleware
├── config.py            # SECRET_KEY, DB_URL, STEAM_API 等配置
├── database.py          # SQLAlchemy 引擎、session、Base、表定义
├── models.py            # Pydantic 请求/响应模型
├── auth.py              # 注册/登录/登出路由 + session 中间件
├── games.py             # 热销榜、推荐、详情 路由
├── ratings.py           # 打分、我的评分 路由
├── steam_sync.py        # Steam API 调用 + APScheduler 定时任务
├── recommender.py       # 推荐引擎（标签相似度 + 协同过滤）
└── requirements.txt

frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.js
    ├── App.vue
    ├── router/index.js
    ├── stores/auth.js
    ├── stores/games.js
    ├── api/index.js
    ├── components/NavBar.vue
    ├── components/GameCard.vue
    ├── components/StarRating.vue
    ├── views/LoginView.vue
    ├── views/RegisterView.vue
    ├── views/HotView.vue
    └── views/RecommendView.vue
```

---

### Task 1: 后端项目初始化

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/config.py`
- Create: `backend/database.py`
- Create: `backend/main.py`

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.0
uvicorn==0.30.0
sqlalchemy==2.0.35
passlib[bcrypt]==1.7.4
python-multipart==0.0.9
httpx==0.27.0
apscheduler==3.10.4
```

- [ ] **Step 2: 安装依赖**

```bash
cd backend && pip install -r requirements.txt
```

- [ ] **Step 3: 创建 config.py**

```python
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'gameplan.db')}"
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
SESSION_DAYS = 7
```

- [ ] **Step 4: 创建 database.py（所有表定义）**

```python
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Date, Float, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

game_tag_assoc = Table(
    "game_tags", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("game_id", Integer, ForeignKey("games.id"), nullable=False),
    Column("tag_id", Integer, ForeignKey("tags.id"), nullable=False),
    UniqueConstraint("game_id", "tag_id"),
)

class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_app_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(256), nullable=False)
    description = Column(Text, default="")
    image_url = Column(String(512), default="")
    price = Column(String(32), default="")
    release_date = Column(String(32), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    tags = relationship("Tag", secondary=game_tag_assoc, back_populates="games")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    games = relationship("Game", secondary=game_tag_assoc, back_populates="tags")

class Rating(Base):
    __tablename__ = "ratings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    score = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "game_id"),)

class DailyTopSeller(Base):
    __tablename__ = "daily_top_sellers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    rank = Column(Integer, nullable=False)
    date = Column(Date, nullable=False)
    snapshot_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class RecommendationHistory(Base):
    __tablename__ = "recommendation_history"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    recommended_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

def init_db():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 4: 创建 main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from database import init_db
from steam_sync import start_scheduler, shutdown_scheduler
from auth import router as auth_router
from games import router as games_router
from ratings import router as ratings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    yield
    shutdown_scheduler()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(games_router, prefix="/api/games", tags=["games"])
app.include_router(ratings_router, prefix="/api/ratings", tags=["ratings"])

@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: 验证后端启动**

```bash
cd backend && uvicorn main:app --reload --port 8000
```
访问 http://localhost:8000/api/health 应返回 `{"status": "ok"}`。

---

### Task 2: 用户认证

**Files:**
- Create: `backend/models.py`
- Create: `backend/auth.py`

- [ ] **Step 1: 创建 models.py（Pydantic schemas）**

```python
from pydantic import BaseModel, Field

class RegisterRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=6, max_length=128)

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str

class GameResponse(BaseModel):
    id: int
    steam_app_id: int
    name: str
    description: str
    image_url: str
    price: str
    tags: list[str] = []

class RatingRequest(BaseModel):
    game_id: int
    score: int = Field(ge=1, le=5)

class RatingResponse(BaseModel):
    game_id: int
    score: int

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    page_size: int
```

- [ ] **Step 2: 创建 auth.py**

```python
from fastapi import APIRouter, HTTPException, Request, Response, Depends
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from database import SessionLocal, User
from models import RegisterRequest, LoginRequest, UserResponse
import secrets

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

SESSION_STORE: dict[str, int] = {}

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in SESSION_STORE:
        raise HTTPException(status_code=401, detail="请先登录")
    user_id = SESSION_STORE[session_id]
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

@router.post("/register", response_model=UserResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = User(username=body.username, password_hash=bcrypt.hash(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserResponse(id=user.id, username=user.username)

@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not bcrypt.verify(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    session_id = secrets.token_hex(32)
    SESSION_STORE[session_id] = user.id
    response.set_cookie(
        key="session_id", value=session_id,
        httponly=True, max_age=7 * 24 * 3600, samesite="lax"
    )
    return UserResponse(id=user.id, username=user.username)

@router.post("/logout")
def logout(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in SESSION_STORE:
        del SESSION_STORE[session_id]
    response.delete_cookie("session_id")
    return {"status": "ok"}

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return UserResponse(id=current_user.id, username=current_user.username)
```

- [ ] **Step 3: 验证认证功能**

```bash
# 启动后端后，用 curl 测试注册和登录
curl -X POST http://localhost:8000/api/auth/register -H "Content-Type: application/json" -d '{"username":"test","password":"123456"}'
curl -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"username":"test","password":"123456"}' -c cookies.txt
curl -b cookies.txt http://localhost:8000/api/auth/me
```

---

### Task 3: Steam 数据同步

**Files:**
- Create: `backend/steam_sync.py`

- [ ] **Step 1: 创建 steam_sync.py**

```python
import httpx
import logging
from datetime import date, datetime, timezone, timedelta
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal, game_tag_assoc, Game, Tag, DailyTopSeller

logger = logging.getLogger(__name__)
STEAM_STORE_API = "https://store.steampowered.com/api"

def fetch_top_sellers() -> list[dict]:
    """拉取 Steam 热销/热门游戏列表"""
    try:
        resp = httpx.get(f"{STEAM_STORE_API}/featuredcategories", timeout=30)
        data = resp.json()
        items = []
        # 尝试从 top_sellers 或 specials 中提取游戏
        for category_key in ["top_sellers", "specials", "coming_soon"]:
            category = data.get(category_key, {})
            for item in category.get("items", [])[:100]:
                items.append({"appid": item.get("id"), "name": item.get("name")})
            if items:
                break
        return items
    except Exception as e:
        logger.error(f"获取热销榜失败: {e}")
        return []

def fetch_game_details(appid: int) -> dict | None:
    """拉取单个游戏详情（标签、描述、价格、封面）"""
    try:
        resp = httpx.get(f"{STEAM_STORE_API}/appdetails?appids={appid}", timeout=30)
        data = resp.json()
        game_data = data.get(str(appid), {}).get("data", {})
        if not game_data.get("name"):
            return None
        tags = []
        for genre in game_data.get("genres", []):
            tags.append(genre.get("description", ""))
        for cat in game_data.get("categories", []):
            tags.append(cat.get("description", ""))
        return {
            "name": game_data["name"],
            "description": game_data.get("short_description", ""),
            "image_url": game_data.get("header_image", ""),
            "price": game_data.get("price_overview", {}).get("final_formatted", "免费"),
            "release_date": game_data.get("release_date", {}).get("date", ""),
            "tags": tags,
        }
    except Exception as e:
        logger.error(f"获取游戏 {appid} 详情失败: {e}")
        return None

def sync_steam_data():
    """定时任务：同步热销榜和游戏详情"""
    db = SessionLocal()
    try:
        logger.info("开始同步 Steam 数据...")
        items = fetch_top_sellers()
        today = date.today()
        existing_ids = {g.steam_app_id for g in db.query(Game.steam_app_id).all()}
        appid_to_game_id = {}

        for rank, item in enumerate(items, 1):
            appid = item["appid"]
            if appid not in existing_ids:
                details = fetch_game_details(appid)
                if not details:
                    continue
                game = Game(
                    steam_app_id=appid,
                    name=details["name"],
                    description=details["description"],
                    image_url=details["image_url"],
                    price=details["price"],
                    release_date=details["release_date"],
                )
                db.add(game)
                db.flush()
                # 插入标签
                for tag_name in details["tags"]:
                    tag = db.query(Tag).filter(Tag.name == tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        db.flush()
                    db.execute(game_tag_assoc.insert().values(game_id=game.id, tag_id=tag.id))
                appid_to_game_id[appid] = game.id
                existing_ids.add(appid)
            else:
                game = db.query(Game).filter(Game.steam_app_id == appid).first()
                # 如果缓存超过7天，刷新详情
                if game.updated_at and (datetime.now(timezone.utc) - game.updated_at.replace(tzinfo=timezone.utc)) > timedelta(days=7):
                    details = fetch_game_details(appid)
                    if details:
                        game.name = details["name"]
                        game.description = details["description"]
                        game.image_url = details["image_url"]
                        game.price = details["price"]
                        game.release_date = details["release_date"]
                        game.updated_at = datetime.now(timezone.utc)
                appid_to_game_id[appid] = game.id

            if appid in appid_to_game_id:
                existing = db.query(DailyTopSeller).filter(
                    DailyTopSeller.game_id == appid_to_game_id[appid],
                    DailyTopSeller.date == today,
                ).first()
                if not existing:
                    db.add(DailyTopSeller(game_id=appid_to_game_id[appid], rank=rank, date=today))

        db.commit()
        logger.info(f"同步完成，共 {len(items)} 款游戏")
    except Exception as e:
        db.rollback()
        logger.error(f"同步失败: {e}")
    finally:
        db.close()

_scheduler = None

def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(sync_steam_data, "cron", hour=2, minute=0)
    _scheduler.start()
    # 首次启动时立即同步一次
    sync_steam_data()

def shutdown_scheduler():
    if _scheduler:
        _scheduler.shutdown()
```

- [ ] **Step 2: 验证数据同步**

重启后端，查看日志确认 Steam 数据同步成功。检查 `gameplan.db` 中 `games`、`tags`、`daily_top_sellers` 表是否有数据：

```bash
sqlite3 backend/gameplan.db "SELECT COUNT(*) FROM games;"
sqlite3 backend/gameplan.db "SELECT COUNT(*) FROM daily_top_sellers;"
```

---

### Task 4: 游戏和评分 API

**Files:**
- Create: `backend/games.py`
- Create: `backend/ratings.py`

- [ ] **Step 1: 创建 games.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from datetime import date
from database import SessionLocal, Game, DailyTopSeller, Tag, RecommendationHistory
from models import GameResponse, PaginatedResponse
from auth import get_current_user, get_db
from recommender import get_recommendations

router = APIRouter()

@router.get("/top-sellers", response_model=PaginatedResponse)
def top_sellers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    today = date.today()
    total = db.query(DailyTopSeller).filter(DailyTopSeller.date == today).count()
    sellers = (
        db.query(DailyTopSeller)
        .filter(DailyTopSeller.date == today)
        .order_by(DailyTopSeller.rank)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = []
    for seller in sellers:
        game = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == seller.game_id).first()
        if game:
            items.append(GameResponse(
                id=game.id,
                steam_app_id=game.steam_app_id,
                name=game.name,
                description=game.description or "",
                image_url=game.image_url or "",
                price=game.price or "",
                tags=[t.name for t in game.tags],
            ))
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/recommended", response_model=PaginatedResponse)
def recommended(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    total, game_ids = get_recommendations(db, current_user.id)
    # 仅对当前页的推荐结果写入历史记录
    start = (page - 1) * page_size
    paged_ids = game_ids[start : start + page_size]
    for gid in paged_ids:
        db.add(RecommendationHistory(user_id=current_user.id, game_id=gid))
    db.commit()
    items = []
    for gid in paged_ids:
        game = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == gid).first()
        if game:
            items.append(GameResponse(
                id=game.id,
                steam_app_id=game.steam_app_id,
                name=game.name,
                description=game.description or "",
                image_url=game.image_url or "",
                price=game.price or "",
                tags=[t.name for t in game.tags],
            ))
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/{game_id}", response_model=GameResponse)
def game_detail(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    return GameResponse(
        id=game.id,
        steam_app_id=game.steam_app_id,
        name=game.name,
        description=game.description or "",
        image_url=game.image_url or "",
        price=game.price or "",
        tags=[t.name for t in game.tags],
    )
```

- [ ] **Step 2: 创建 ratings.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, Game, Rating
from models import RatingRequest, RatingResponse
from auth import get_current_user, get_db

router = APIRouter()

@router.post("/", response_model=RatingResponse)
def create_rating(
    body: RatingRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    game = db.query(Game).filter(Game.id == body.game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")
    existing = db.query(Rating).filter(
        Rating.user_id == current_user.id,
        Rating.game_id == body.game_id,
    ).first()
    if existing:
        existing.score = body.score
        db.commit()
    else:
        db.add(Rating(user_id=current_user.id, game_id=body.game_id, score=body.score))
        db.commit()
    return RatingResponse(game_id=body.game_id, score=body.score)

@router.get("/mine", response_model=list[RatingResponse])
def my_ratings(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    ratings = db.query(Rating).filter(Rating.user_id == current_user.id).all()
    return [RatingResponse(game_id=r.game_id, score=r.score) for r in ratings]
```

- [ ] **Step 3: 创建 recommender.py（占位，Task 5 实现）**

```python
def get_recommendations(db, user_id: int) -> tuple[int, list[int]]:
    """返回 (total, game_ids)。cold start 时返回热销榜 Top 100"""
    from datetime import date
    from database import DailyTopSeller
    today = date.today()
    sellers = (
        db.query(DailyTopSeller)
        .filter(DailyTopSeller.date == today)
        .order_by(DailyTopSeller.rank)
        .limit(100)
        .all()
    )
    game_ids = [s.game_id for s in sellers]
    return len(game_ids), game_ids
```

- [ ] **Step 4: 验证游戏 API**

```bash
curl -b cookies.txt "http://localhost:8000/api/games/top-sellers?page=1&page_size=5"
```

---

### Task 5: 推荐引擎

**Files:**
- Rewrite: `backend/recommender.py`

- [ ] **Step 1: 实现完整推荐引擎**

```python
from datetime import date
from sqlalchemy.orm import Session
from database import Rating, Game, DailyTopSeller, RecommendationHistory

def get_recommendations(db: Session, user_id: int) -> tuple[int, list[int]]:
    # 用户评分数量
    rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()

    # 冷启动：热销榜 Top 100
    if rating_count < 5:
        today = date.today()
        sellers = (
            db.query(DailyTopSeller)
            .filter(DailyTopSeller.date == today)
            .order_by(DailyTopSeller.rank)
            .limit(100)
            .all()
        )
        game_ids = [s.game_id for s in sellers]
        return len(game_ids), game_ids

    # === 获取所有用户评分数据 ===
    all_ratings = db.query(Rating).all()

    # 构建用户-游戏评分矩阵: {user_id: {game_id: score}}
    user_scores = {}
    for r in all_ratings:
        user_scores.setdefault(r.user_id, {})[r.game_id] = r.score

    current_scores = user_scores.get(user_id, {})
    rated_game_ids = set(current_scores.keys())

    # === 标签相似度 ===
    high_rated = [gid for gid, s in current_scores.items() if s >= 4]
    all_games = db.query(Game).all()
    game_tag_sets = {}
    for g in all_games:
        game_tag_sets[g.id] = {t.name for t in g.tags}

    high_rated_tags = set()
    for gid in high_rated:
        high_rated_tags |= game_tag_sets.get(gid, set())

    tag_scores = {}
    for g in all_games:
        if g.id in rated_game_ids:
            continue
        g_tags = game_tag_sets.get(g.id, set())
        if not high_rated_tags or not g_tags:
            tag_scores[g.id] = 0.0
        else:
            intersection = len(high_rated_tags & g_tags)
            union = len(high_rated_tags | g_tags)
            tag_scores[g.id] = intersection / union if union > 0 else 0.0

    # === 协同过滤 ===
    cf_scores = {}
    other_users = [uid for uid in user_scores if uid != user_id]
    current_vec = _rating_vector(current_scores)

    if other_users and current_vec:
        similarities = []
        for ouid in other_users:
            other_vec = _rating_vector(user_scores[ouid])
            if not other_vec:
                continue
            sim = _cosine_similarity(current_vec, other_vec)
            similarities.append((ouid, sim))
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_similar = similarities[:10]

        # 聚合相似用户的高分游戏
        cf_accum = {}
        for ouid, sim in top_similar:
            for gid, score in user_scores[ouid].items():
                if score >= 4 and gid not in rated_game_ids:
                    cf_accum.setdefault(gid, []).append(sim)
        for gid, sims in cf_accum.items():
            cf_scores[gid] = sum(sims) / len(sims) if sims else 0.0

    # === 混合打分 ===
    final_scores = {}
    for gid in set(list(tag_scores.keys()) + list(cf_scores.keys())):
        final_scores[gid] = tag_scores.get(gid, 0) * 0.6 + cf_scores.get(gid, 0) * 0.4

    # === 去重与降权 ===
    history = db.query(RecommendationHistory).filter(
        RecommendationHistory.user_id == user_id
    ).all()
    history_game_ids = {h.game_id for h in history}

    for gid in list(final_scores.keys()):
        if gid in history_game_ids:
            final_scores[gid] *= 0.5

    sorted_games = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
    game_ids = [gid for gid, _ in sorted_games if gid not in rated_game_ids]

    return len(game_ids), game_ids


def _rating_vector(scores: dict[int, int]) -> dict[int, float] | None:
    if not scores:
        return None
    mean = sum(scores.values()) / len(scores)
    return {gid: s - mean for gid, s in scores.items()}


def _cosine_similarity(a: dict[int, float], b: dict[int, float]) -> float:
    common = set(a.keys()) & set(b.keys())
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    norm_a = sum(v ** 2 for v in a.values()) ** 0.5
    norm_b = sum(v ** 2 for v in b.values()) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
```

- [ ] **Step 2: 验证推荐逻辑**

创建几个测试用户和评分，确认推荐接口返回结果：

```bash
# 注册多个用户，对游戏打分，然后查看推荐
curl -b cookies.txt "http://localhost:8000/api/games/recommended?page=1&page_size=5"
```

---

### Task 6: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.js`
- Create: `frontend/index.html`
- Create: `frontend/src/main.js`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/router/index.js`
- Create: `frontend/src/api/index.js`
- Create: `frontend/src/stores/auth.js`
- Create: `frontend/src/stores/games.js`

- [ ] **Step 1: 初始化 Vue 项目**

```bash
cd frontend && npm create vite@latest . -- --template vue
```

- [ ] **Step 2: 安装依赖**

```bash
cd frontend && npm install && npm install vue-router@4 pinia@2
```

- [ ] **Step 3: 配置 vite.config.js**

```js
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

- [ ] **Step 4: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>GamePlan - 游戏推荐</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.js"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 src/main.js**

```js
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
```

- [ ] **Step 6: 创建 src/App.vue**

```vue
<template>
  <NavBar />
  <main class="container">
    <router-view />
  </main>
</template>

<script setup>
import NavBar from './components/NavBar.vue'
</script>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #1a1a2e; color: #eee; }
.container { max-width: 1200px; margin: 0 auto; padding: 20px; }
</style>
```

- [ ] **Step 7: 创建 src/router/index.js**

```js
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: '/hot' },
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/register', name: 'Register', component: () => import('../views/RegisterView.vue') },
  { path: '/hot', name: 'Hot', component: () => import('../views/HotView.vue') },
  { path: '/recommend', name: 'Recommend', component: () => import('../views/RecommendView.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
```

- [ ] **Step 8: 创建 src/api/index.js**

```js
const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: '请求失败' }))
    throw new Error(err.detail || '请求失败')
  }
  return res.json()
}

export const api = {
  register: (body) => request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  logout: () => request('/auth/logout', { method: 'POST' }),
  me: () => request('/auth/me'),
  topSellers: (page = 1, pageSize = 20) => request(`/games/top-sellers?page=${page}&page_size=${pageSize}`),
  recommended: (page = 1, pageSize = 20) => request(`/games/recommended?page=${page}&page_size=${pageSize}`),
  rate: (gameId, score) => request('/ratings/', { method: 'POST', body: JSON.stringify({ game_id: gameId, score }) }),
  myRatings: () => request('/ratings/mine'),
}
```

- [ ] **Step 9: 创建 src/stores/auth.js**

```js
import { defineStore } from 'pinia'
import { api } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null, loading: false }),
  actions: {
    async checkAuth() {
      try {
        this.user = await api.me()
      } catch {
        this.user = null
      }
    },
    async login(username, password) {
      this.user = await api.login({ username, password })
    },
    async register(username, password) {
      this.user = await api.register({ username, password })
    },
    async logout() {
      await api.logout()
      this.user = null
    },
  },
})
```

- [ ] **Step 10: 创建 src/stores/games.js**

```js
import { defineStore } from 'pinia'
import { api } from '../api'

export const useGamesStore = defineStore('games', {
  state: () => ({
    hotGames: [],
    hotTotal: 0,
    recGames: [],
    recTotal: 0,
    myRatings: {},
  }),
  actions: {
    async loadHot(page = 1, pageSize = 20) {
      const data = await api.topSellers(page, pageSize)
      this.hotGames = data.items
      this.hotTotal = data.total
    },
    async loadRecommended(page = 1, pageSize = 20) {
      const data = await api.recommended(page, pageSize)
      this.recGames = data.items
      this.recTotal = data.total
    },
    async rate(gameId, score) {
      await api.rate(gameId, score)
      this.myRatings[gameId] = score
    },
    async loadMyRatings() {
      const ratings = await api.myRatings()
      for (const r of ratings) {
        this.myRatings[r.game_id] = r.score
      }
    },
  },
})
```

- [ ] **Step 11: 验证前端启动**

```bash
cd frontend && npm run dev
```
访问 http://localhost:5173 确认空白页面加载成功（路由跳转到 /hot）。

---

### Task 7: 前端组件

**Files:**
- Create: `frontend/src/components/NavBar.vue`
- Create: `frontend/src/components/GameCard.vue`
- Create: `frontend/src/components/StarRating.vue`

- [ ] **Step 1: 创建 StarRating.vue**

```vue
<template>
  <span class="star-rating">
    <button
      v-for="n in 5" :key="n"
      class="star" :class="{ active: n <= modelValue }"
      @click="$emit('update:modelValue', n)"
    >★</button>
  </span>
</template>

<script setup>
defineProps({ modelValue: { type: Number, default: 0 } })
defineEmits(['update:modelValue'])
</script>

<style scoped>
.star { background: none; border: none; font-size: 24px; color: #555; cursor: pointer; padding: 0 2px; }
.star.active { color: #f5c518; }
.star:hover { color: #f5c518; }
</style>
```

- [ ] **Step 2: 创建 GameCard.vue**

```vue
<template>
  <div class="game-card">
    <img :src="game.image_url" :alt="game.name" class="game-image" />
    <div class="game-info">
      <h3>{{ game.name }}</h3>
      <div class="tags">
        <span v-for="tag in game.tags.slice(0, 5)" :key="tag" class="tag">{{ tag }}</span>
      </div>
      <div class="price">{{ game.price }}</div>
      <StarRating v-model="rating" @update:model-value="onRate" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import StarRating from './StarRating.vue'
import { useGamesStore } from '../stores/games'

const props = defineProps({ game: Object })
const store = useGamesStore()

const rating = ref(store.myRatings[props.game.id] || 0)

watch(() => store.myRatings[props.game.id], (val) => {
  if (val !== undefined) rating.value = val
})

function onRate(score) {
  store.rate(props.game.id, score)
}
</script>

<style scoped>
.game-card { display: flex; gap: 16px; background: #16213e; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
.game-image { width: 184px; height: 104px; object-fit: cover; border-radius: 8px; flex-shrink: 0; }
.game-info h3 { font-size: 18px; margin-bottom: 8px; }
.tags { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 8px; }
.tag { background: #0f3460; padding: 2px 8px; border-radius: 4px; font-size: 12px; color: #ccc; }
.price { color: #a8e6cf; font-size: 14px; margin-bottom: 8px; }
</style>
```

- [ ] **Step 3: 创建 NavBar.vue**

```vue
<template>
  <nav class="navbar">
    <router-link to="/" class="logo">GamePlan</router-link>
    <div class="nav-links">
      <router-link to="/hot">热销榜</router-link>
      <router-link v-if="auth.user" to="/recommend">推荐</router-link>
    </div>
    <div class="nav-right">
      <template v-if="auth.user">
        <span class="username">{{ auth.user.username }}</span>
        <button @click="onLogout">退出</button>
      </template>
      <template v-else>
        <router-link to="/login">登录</router-link>
        <router-link to="/register">注册</router-link>
      </template>
    </div>
  </nav>
</template>

<script setup>
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

async function onLogout() {
  await auth.logout()
  router.push('/hot')
}
</script>

<style scoped>
.navbar { display: flex; align-items: center; gap: 20px; padding: 12px 24px; background: #0f3460; }
.logo { font-size: 22px; font-weight: 700; color: #e94560; text-decoration: none; }
.nav-links a { color: #ccc; text-decoration: none; font-size: 15px; }
.nav-right { margin-left: auto; display: flex; align-items: center; gap: 12px; }
.nav-right a { color: #ccc; text-decoration: none; }
.username { color: #a8e6cf; }
button { background: #e94560; color: #fff; border: none; padding: 6px 14px; border-radius: 6px; cursor: pointer; }
</style>
```

---

### Task 8: 前端页面

**Files:**
- Create: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/RegisterView.vue`
- Create: `frontend/src/views/HotView.vue`
- Create: `frontend/src/views/RecommendView.vue`

- [ ] **Step 1: 创建 LoginView.vue**

```vue
<template>
  <div class="auth-form">
    <h2>登录</h2>
    <form @submit.prevent="onLogin">
      <input v-model="username" placeholder="用户名" required />
      <input v-model="password" type="password" placeholder="密码" required />
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">登录</button>
    </form>
    <p>还没有账号？<router-link to="/register">注册</router-link></p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function onLogin() {
  loading.value = true
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/hot')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-form { max-width: 400px; margin: 60px auto; background: #16213e; padding: 32px; border-radius: 12px; }
h2 { margin-bottom: 20px; }
input { display: block; width: 100%; padding: 10px; margin-bottom: 12px; border: 1px solid #333; border-radius: 6px; background: #1a1a2e; color: #eee; }
button { width: 100%; padding: 10px; background: #e94560; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }
button:disabled { opacity: 0.6; }
.error { color: #e94560; margin-bottom: 12px; }
</style>
```

- [ ] **Step 2: 创建 RegisterView.vue**

```vue
<template>
  <div class="auth-form">
    <h2>注册</h2>
    <form @submit.prevent="onRegister">
      <input v-model="username" placeholder="用户名" required />
      <input v-model="password" type="password" placeholder="密码（至少6位）" required />
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="loading">注册</button>
    </form>
    <p>已有账号？<router-link to="/login">登录</router-link></p>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function onRegister() {
  loading.value = true
  error.value = ''
  try {
    await auth.register(username.value, password.value)
    router.push('/hot')
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-form { max-width: 400px; margin: 60px auto; background: #16213e; padding: 32px; border-radius: 12px; }
h2 { margin-bottom: 20px; }
input { display: block; width: 100%; padding: 10px; margin-bottom: 12px; border: 1px solid #333; border-radius: 6px; background: #1a1a2e; color: #eee; }
button { width: 100%; padding: 10px; background: #e94560; color: #fff; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; }
button:disabled { opacity: 0.6; }
.error { color: #e94560; margin-bottom: 12px; }
</style>
```

- [ ] **Step 3: 创建 HotView.vue**

```vue
<template>
  <div>
    <h2 class="page-title">Steam 今日热销榜</h2>
    <GameCard v-for="game in store.hotGames" :key="game.id" :game="game" />
    <div class="pagination">
      <button :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
      <span>第 {{ page }} / {{ maxPage }} 页</span>
      <button :disabled="page >= maxPage" @click="changePage(page + 1)">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import GameCard from '../components/GameCard.vue'
import { useGamesStore } from '../stores/games'

const store = useGamesStore()
const page = ref(1)
const pageSize = 20

const maxPage = computed(() => Math.ceil(store.hotTotal / pageSize) || 1)

function changePage(p) {
  page.value = p
  store.loadHot(p, pageSize)
  window.scrollTo(0, 0)
}

onMounted(() => store.loadHot(1, pageSize))
</script>

<style scoped>
.page-title { font-size: 24px; margin-bottom: 20px; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; }
.pagination button { background: #0f3460; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.pagination button:disabled { opacity: 0.4; cursor: default; }
</style>
```

- [ ] **Step 4: 创建 RecommendView.vue**

```vue
<template>
  <div>
    <h2 class="page-title">为你推荐</h2>
    <div v-if="!auth.user" class="need-login">请先<router-link to="/login">登录</router-link>以获取推荐</div>
    <template v-else>
      <GameCard v-for="game in store.recGames" :key="game.id" :game="game" />
      <div v-if="store.recGames.length === 0" class="empty">评分不足，请先在热销榜中为至少 5 款游戏打分</div>
      <div class="pagination" v-if="store.recTotal > pageSize">
        <button :disabled="page <= 1" @click="changePage(page - 1)">上一页</button>
        <span>第 {{ page }} / {{ maxPage }} 页</span>
        <button :disabled="page >= maxPage" @click="changePage(page + 1)">下一页</button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import GameCard from '../components/GameCard.vue'
import { useAuthStore } from '../stores/auth'
import { useGamesStore } from '../stores/games'

const auth = useAuthStore()
const store = useGamesStore()
const page = ref(1)
const pageSize = 20

const maxPage = computed(() => Math.ceil(store.recTotal / pageSize) || 1)

function changePage(p) {
  page.value = p
  store.loadRecommended(p, pageSize)
  window.scrollTo(0, 0)
}

onMounted(async () => {
  await auth.checkAuth()
  if (auth.user) {
    await store.loadMyRatings()
    store.loadRecommended(1, pageSize)
  }
})
</script>

<style scoped>
.page-title { font-size: 24px; margin-bottom: 20px; }
.need-login, .empty { text-align: center; color: #888; padding: 40px; }
.pagination { display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 20px; }
.pagination button { background: #0f3460; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; }
.pagination button:disabled { opacity: 0.4; cursor: default; }
</style>
```

- [ ] **Step 5: 路由守卫：更新 router/index.js**

在 `src/router/index.js` 中添加导航守卫，require `src/stores/auth.js`:

```js
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const routes = [
  { path: '/', redirect: '/hot' },
  { path: '/login', name: 'Login', component: () => import('../views/LoginView.vue') },
  { path: '/register', name: 'Register', component: () => import('../views/RegisterView.vue') },
  { path: '/hot', name: 'Hot', component: () => import('../views/HotView.vue') },
  { path: '/recommend', name: 'Recommend', component: () => import('../views/RecommendView.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, from, next) => {
  const auth = useAuthStore()
  if (!auth.user) {
    try { await auth.checkAuth() } catch {}
  }
  if (to.meta.requiresAuth && !auth.user) {
    next('/login')
  } else {
    next()
  }
})

export default router
```

- [ ] **Step 6: 验证前端完整功能**

```bash
cd frontend && npm run dev
```

1. 访问 http://localhost:5173 → 跳转到 /hot，显示游戏列表
2. 注册账号 → 自动登录
3. 对 5 款以上游戏打分
4. 切换到 /recommend → 显示推荐游戏
5. 刷新页面 → 推荐更新，之前见过的游戏权重降低

---

### Task 9: 部署配置

**Files:**
- Create: `nginx.conf`

- [ ] **Step 1: 构建前端**

```bash
cd frontend && npm run build
```

产物在 `frontend/dist/`。

- [ ] **Step 2: 创建 nginx.conf**

```nginx
server {
    listen 80;
    server_name _;

    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location / {
        root /path/to/frontend/dist;
        index index.html;
        try_files $uri $uri/ /index.html;
    }
}
```

- [ ] **Step 3: 启动生产环境**

```bash
# 启动后端（生产模式）
cd backend && uvicorn main:app --host 127.0.0.1 --port 8000

# 配置 nginx 并启动
sudo cp nginx.conf /etc/nginx/sites-available/gameplan
sudo ln -s /etc/nginx/sites-available/gameplan /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 备注

- MVP 不使用密码重置、邮箱验证等功能
- Session 存储为内存 dict，重启后所有用户需重新登录。生产环境应换为 Redis 或数据库 session
- Steam API 返回数据可能因地区不同有差异，需根据实际返回调整字段解析
