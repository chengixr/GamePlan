import os
import json as _json
import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from config import BACKEND_PORT, FRONTEND_PORT
from database import init_db, SessionLocal
from seed_data import seed
from logger_config import setup_logging, clean_old_logs

setup_logging()
logger = logging.getLogger("main")
from auth import router as auth_router
from games import router as games_router
from ratings import router as ratings_router
from steam_sync import start_scheduler, shutdown_scheduler

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed()
    clean_old_logs()
    start_scheduler()
    # 预热缓存
    from recommender import _get_game_tag_sets
    db = SessionLocal()
    try:
        _get_game_tag_sets(db)
        logger.info("缓存预热完成")
    finally:
        db.close()
    logger.info("GamePlan 服务启动")
    yield
    shutdown_scheduler()
    logger.info("GamePlan 服务关闭")

app = FastAPI(lifespan=lifespan)

# 请求日志中间件
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    # 仅记录写操作（POST/PUT/DELETE）和服务端错误（5xx）
    if request.method in ("POST", "PUT", "DELETE") or response.status_code >= 500:
        elapsed = (time.time() - start) * 1000
        logger = logging.getLogger("api")
        level = logging.INFO if response.status_code < 400 else logging.WARNING
        logger.log(level, f"{request.method} {request.url.path} → {response.status_code} ({elapsed:.0f}ms)")
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        f"http://localhost:{FRONTEND_PORT}",
        f"http://localhost:{BACKEND_PORT}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(games_router, prefix="/api/games", tags=["games"])
app.include_router(ratings_router, prefix="/api/ratings", tags=["ratings"])
from favorites import router as favorites_router
app.include_router(favorites_router, prefix="/api/favorites", tags=["favorites"])
from admin import router as admin_router
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])

from threading import Thread

@app.post("/api/sync")
def trigger_sync():
    """手动触发一次 Steam 数据同步（后台执行）"""
    from steam_sync import sync_steam_data
    t = Thread(target=sync_steam_data, daemon=True)
    t.start()
    return {"status": "started", "message": "同步任务已在后台启动，查看日志获取进度"}

STATIC_IMAGES = os.path.join(os.path.dirname(__file__), "static", "images")
os.makedirs(STATIC_IMAGES, exist_ok=True)
app.mount("/static/images", StaticFiles(directory=STATIC_IMAGES), name="static_images")

@app.post("/api/llm/build-embeddings")
def build_embeddings():
    from llm import get_embedding, embedding_available
    from database import SessionLocal, Game, GameEmbedding

    if not embedding_available():
        return {"status": "unavailable", "message": "LLM 未配置或不可用"}

    db = SessionLocal()
    try:
        games = db.query(Game).outerjoin(GameEmbedding, Game.id == GameEmbedding.game_id).filter(GameEmbedding.game_id == None, Game.description != "").all()
        built = 0
        for g in games:
            desc = (g.description or "")[:2000]
            if len(desc) < 50:
                continue
            emb = get_embedding(desc)
            if emb:
                db.merge(GameEmbedding(game_id=g.id, embedding=_json.dumps(emb)))
                built += 1
                if built % 10 == 0:
                    db.commit()
        db.commit()
        return {"status": "ok", "built": built, "total": len(games)}
    finally:
        db.close()

@app.get("/api/health")
def health():
    return {"status": "ok"}

# 生产模式：托管前端静态文件
if os.path.isdir(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        """SPA fallback：所有非 /api 请求返回 index.html"""
        file_path = os.path.join(FRONTEND_DIST, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIST, "index.html"))
