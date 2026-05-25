import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from config import BACKEND_PORT, FRONTEND_PORT
from database import init_db
from seed_data import seed
from auth import router as auth_router
from games import router as games_router
from ratings import router as ratings_router
from steam_sync import start_scheduler, shutdown_scheduler

FRONTEND_DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed()
    start_scheduler()
    yield
    shutdown_scheduler()

app = FastAPI(lifespan=lifespan)

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
