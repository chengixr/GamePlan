from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from datetime import date, datetime, timedelta
import json
import re
import threading
from database import SessionLocal, Game, DailyTopSeller, SteamRanking, Tag
from sqlalchemy import func
from models import GameResponse, PaginatedResponse
from auth import get_current_user, get_db
from recommender import get_recommendations

router = APIRouter()

# 热销榜缓存（5 分钟 TTL）
_cache = {}
_cache_lock = threading.Lock()

def clear_hot_cache():
    """同步后清除缓存"""
    with _cache_lock:
        _cache.clear()

@router.get("/tags")
def list_tags(db: Session = Depends(get_db)):
    tags = db.query(Tag).all()
    return [{"id": t.id, "name": t.name} for t in tags]

@router.get("/top-sellers", response_model=PaginatedResponse)
def top_sellers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    cache_key = "ts_latest"

    with _cache_lock:
        cache_entry = _cache.get(cache_key)
        if cache_entry and cache_entry["expires"] > datetime.now():
            all_items, total = cache_entry["data"]
        else:
            # 获取最新一次快照时间
            latest = db.query(func.max(SteamRanking.snapshot_time)).scalar()
            if not latest:
                _cache[cache_key] = {"data": ([], 0), "expires": datetime.now() + timedelta(minutes=5)}
                return PaginatedResponse(items=[], total=0, page=page, page_size=page_size)

            rankings = (
                db.query(SteamRanking)
                .filter(SteamRanking.snapshot_time == latest)
                .order_by(SteamRanking.rank)
                .all()
            )
            if not rankings:
                _cache[cache_key] = {"data": ([], 0), "expires": datetime.now() + timedelta(minutes=5)}
                return PaginatedResponse(items=[], total=0, page=page, page_size=page_size)

            # 批量查找 Game 表（IN 查询）
            appids = [r.steam_app_id for r in rankings]
            games_map = {
                g.steam_app_id: g
                for g in db.query(Game).options(joinedload(Game.tags))
                .filter(Game.steam_app_id.in_(appids)).all()
            }

            total = len(rankings)
            all_items = []
            for r in rankings:
                game = games_map.get(r.steam_app_id)
                if game:
                    # 图片回退：仅使用本地存在的截图
                    fallback = ""
                    try:
                        ss = json.loads(game.screenshots or "[]")
                        for s in ss:
                            if s.startswith("/static/"):
                                fallback = s
                                break
                    except Exception:
                        pass

                    all_items.append(GameResponse(
                        id=game.id, steam_app_id=game.steam_app_id,
                        name=game.name, name_cn=game.name_cn or "",
                        description=game.description or "",
                        image_url=game.image_url or "",
                        fallback_image=fallback,
                        price=game.price or "",
                        tags=[t.name for t in game.tags],
                    ))
            _cache[cache_key] = {"data": (all_items, total), "expires": datetime.now() + timedelta(minutes=5)}

    start = (page - 1) * page_size
    paged = all_items[start:start + page_size] if all_items else []
    return PaginatedResponse(items=paged, total=total, page=page, page_size=page_size)

@router.get("/recommended", response_model=PaginatedResponse)
def recommended(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    total, game_ids = get_recommendations(db, current_user.id)
    start = (page - 1) * page_size
    paged_ids = game_ids[start : start + page_size]
    items = []
    for gid in paged_ids:
        game = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == gid).first()
        if game:
            fallback = ""
            try:
                ss = json.loads(game.screenshots or "[]")
                for s in ss:
                    if s.startswith("/static/"):
                        fallback = s
                        break
            except Exception:
                pass

            items.append(GameResponse(
                id=game.id,
                steam_app_id=game.steam_app_id,
                name=game.name,
                name_cn=game.name_cn or "",
                description=game.description or "",
                image_url=game.image_url or "",
                fallback_image=fallback,
                price=game.price or "",
                tags=[t.name for t in game.tags],
            ))
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/top-sellers/history")
def top_sellers_history(
    target_date: str = Query(..., description="日期 YYYY-MM-DD"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """按日期查询历史热销榜"""
    try:
        dt = date.fromisoformat(target_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式应为 YYYY-MM-DD")

    total = db.query(DailyTopSeller).filter(DailyTopSeller.date == dt).count()
    sellers = (
        db.query(DailyTopSeller)
        .filter(DailyTopSeller.date == dt)
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
                name_cn=game.name_cn or "",
                description=game.description or "",
                image_url=game.image_url or "",
                price=game.price or "",
                tags=[t.name for t in game.tags],
            ))
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

@router.get("/top-sellers/dates")
def top_sellers_dates(db: Session = Depends(get_db)):
    """列出所有有热销榜记录的日期"""
    from sqlalchemy import func, distinct
    dates = db.query(distinct(DailyTopSeller.date)).order_by(DailyTopSeller.date.desc()).limit(30).all()
    return [d[0].isoformat() for d in dates]

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

@router.get("/{game_id}")
def game_detail(game_id: int, db: Session = Depends(get_db)):
    game = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == game_id).first()
    if not game:
        raise HTTPException(status_code=404, detail="游戏不存在")

    screenshots = []
    review_positive = 0
    review_total = 0
    try:
        if game.screenshots:
            screenshots = json.loads(game.screenshots)
    except: pass
    try:
        if game.review_summary:
            rd = json.loads(game.review_summary)
            review_positive = rd.get("positive", 0)
            review_total = rd.get("total", 0)
    except: pass

    similar = []
    try:
        from recommender import get_similar_games
        similar_ids = get_similar_games(db, game_id, limit=6)
        for gid in similar_ids:
            sg = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == gid).first()
            if sg:
                similar.append(GameResponse(
                    id=sg.id, steam_app_id=sg.steam_app_id, name=sg.name,
                    name_cn=sg.name_cn or "", description=sg.description or "",
                    image_url=sg.image_url or "", price=sg.price or "",
                    tags=[t.name for t in sg.tags],
                ))
    except: pass

    return {
        "id": game.id, "steam_app_id": game.steam_app_id,
        "name": game.name, "name_cn": game.name_cn or "",
        "description": game.description or "",
        "image_url": game.image_url or "",
        "price": game.price or "",
        "release_date": game.release_date or "",
        "tags": [t.name for t in game.tags],
        "screenshots": screenshots,
        "review_positive": review_positive,
        "review_total": review_total,
        "user_reviews": json.loads(game.user_reviews or "[]"),
        "similar_games": similar,
    }
