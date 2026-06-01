import os
import json
import logging
from datetime import date, datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import SessionLocal, User, Rating, Game, DailyTopSeller, UserSession
from models import AdminUserResponse, AdminSyncStatusResponse, AdminLogResponse, AdminSchedulerJobResponse
from auth import require_admin, get_db
from steam_sync import sync_steam_data, _scheduler, get_job_status

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
            avatar=u.avatar or "1", is_active=u.is_active, is_admin=u.is_admin, rating_count=count,
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

@router.put("/users/{user_id}/admin")
def toggle_user_admin(
    user_id: int,
    body: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.id == admin.id:
        raise HTTPException(400, "不能修改自己的管理员权限")
    user.is_admin = body.get("is_admin", False)
    db.commit()
    return {"status": "ok", "is_admin": user.is_admin}

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
    # 删除关联数据
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

# ========== 定时任务 ==========

_JOB_META = {
    "sync_rankings": {"name": "排名快照同步", "description": "每小时从 Steam 搜索页抓取热销前 100 名排名，缺失游戏自动拉取详情入库", "cron": "每小时第 13 分"},
    "sync_steam_data": {"name": "完整数据同步", "description": "多源同步（API+搜索+SteamCharts），更新游戏详情、截图、标签、评价", "cron": "每天 00:17, 06:17, 12:17, 18:17 (UTC)"},
    "catchup_sync": {"name": "追补同步", "description": "补录当天缺失的排名记录，补充数据不完整游戏的截图/描述/标签", "cron": "每天 19:17 (UTC)"},
    "clean_old_logs": {"name": "日志清理", "description": "清理 30 天前的过期日志文件", "cron": "每天 03:00 (UTC)"},
}

@router.get("/scheduler/jobs")
def list_scheduler_jobs(admin: User = Depends(require_admin)):
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

@router.post("/scheduler/jobs/{job_id}/trigger")
def trigger_scheduler_job(job_id: str, admin: User = Depends(require_admin)):
    if not _scheduler:
        raise HTTPException(503, "调度器未启动")

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

@router.get("/sync/stats")
def sync_stats(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    today = date.today()
    total_games = db.query(func.count(Game.id)).scalar()
    total_ratings = db.query(func.count(Rating.id)).scalar()
    today_ranked = db.query(func.count(DailyTopSeller.id)).filter(DailyTopSeller.date == today).scalar()

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

    if not os.path.isfile(log_file):
        log_file = os.path.join(LOG_DIR, "gameplan.log")

    raw_lines = []
    if os.path.isfile(log_file):
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = [line.rstrip("\n") for line in f.readlines()]

    if level != "ALL":
        raw_lines = [l for l in raw_lines if f"[{level}]" in l]

    total = len(raw_lines)
    recent = raw_lines[-lines:]

    return {"lines": recent, "total": total, "file": os.path.basename(log_file)}
