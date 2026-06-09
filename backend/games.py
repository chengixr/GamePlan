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

# HTML 净化：移除危险标签和事件处理器（深度防御，Steam 描述为可信来源）
_DANGEROUS_RE = re.compile(
    r'<script[\s>]|</script>|<iframe[\s>]|</iframe>',
    re.IGNORECASE,
)
_EVENT_ATTR_RE = re.compile(r'\s+on\w+\s*=\s*"[^"]*"', re.IGNORECASE)
_JAVASCRIPT_URL_RE = re.compile(r'href\s*=\s*"javascript:', re.IGNORECASE)


def _sanitize_html(text: str) -> str:
    if not text:
        return text
    text = _DANGEROUS_RE.sub('', text)
    text = _EVENT_ATTR_RE.sub('', text)
    text = _JAVASCRIPT_URL_RE.sub('href="#"', text)
    return text


# 热销榜缓存（5 分钟 TTL）
_cache = {}
_cache_lock = threading.Lock()

def clear_hot_cache():
    """同步后清除缓存"""
    with _cache_lock:
        _cache.clear()

@router.get("/tags")
def list_tags(
    limit: int = Query(10, ge=1, le=50, description="返回数量"),
    db: Session = Depends(get_db),
):
    """返回热门标签（按关联游戏数降序）"""
    from database import game_tag_assoc as gta
    from sqlalchemy import desc
    tags = (
        db.query(Tag, func.count(gta.c.game_id).label("cnt"))
        .outerjoin(gta, Tag.id == gta.c.tag_id)
        .group_by(Tag.id)
        .order_by(desc("cnt"))
        .limit(limit)
        .all()
    )
    return [{"id": t.id, "name": t.name, "count": cnt} for t, cnt in tags]


@router.get("/search", response_model=PaginatedResponse)
def search_games(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """按游戏名称搜索（中英文）"""
    keyword = f"%{q}%"
    base = db.query(Game).options(joinedload(Game.tags)).filter(
        (Game.name.like(keyword)) | (Game.name_cn.like(keyword))
    )
    total = base.count()
    games = base.order_by(Game.name).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for game in games:
        items.append(GameResponse(
            id=game.id, steam_app_id=game.steam_app_id,
            name=game.name, name_cn=game.name_cn or "",
            description=_sanitize_html(game.description or ""),
            image_url=game.image_url or "",
            image_large=game.image_large or game.image_url or "",
            fallback_image=game.fallback_image or "",
            price=game.price or "",
            tags=[t.name for t in game.tags],
        ))
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size)

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
                    all_items.append(GameResponse(
                        id=game.id, steam_app_id=game.steam_app_id,
                        name=game.name, name_cn=game.name_cn or "",
                        description=_sanitize_html(game.description or ""),
                        image_url=game.image_url or "",
                        image_large=game.image_large or game.image_url or "",
                        fallback_image=game.fallback_image or "",
                        price=game.price or "",
                        tags=[t.name for t in game.tags],
                    ))
            _cache[cache_key] = {"data": (all_items, total), "expires": datetime.now() + timedelta(minutes=5)}

    start = (page - 1) * page_size
    paged = all_items[start:start + page_size] if all_items else []
    return PaginatedResponse(items=paged, total=total, page=page, page_size=page_size)


@router.get("/recommended")
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
            # 写入推荐历史（已存在则忽略，避免重复降权）
            from database import RecommendationHistory
            existing = db.query(RecommendationHistory).filter(
                RecommendationHistory.user_id == current_user.id,
                RecommendationHistory.game_id == gid,
            ).first()
            if not existing:
                db.add(RecommendationHistory(user_id=current_user.id, game_id=gid))
            items.append(GameResponse(
                id=game.id,
                steam_app_id=game.steam_app_id,
                name=game.name,
                name_cn=game.name_cn or "",
                description=_sanitize_html(game.description or ""),
                image_url=game.image_url or "",
                image_large=game.image_large or game.image_url or "",
                fallback_image=game.fallback_image or "",
                price=game.price or "",
                tags=[t.name for t in game.tags],
            ))
    db.commit()

    # 推荐解释：列出影响推荐的高分游戏
    from database import Rating
    high_rated = db.query(Rating.game_id).filter(
        Rating.user_id == current_user.id, Rating.score >= 4
    ).order_by(Rating.score.desc()).limit(3).all()
    hr_ids = [r[0] for r in high_rated]
    hr_games = db.query(Game.id, Game.name, Game.name_cn).filter(Game.id.in_(hr_ids)).all()
    hr_map = {g.id: g.name_cn or g.name for g in hr_games}
    rec_explanation = [hr_map[gid] for gid in hr_ids if gid in hr_map]

    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "rec_explanation": rec_explanation,
    }


@router.post("/{game_id}/dismiss")
def dismiss_game(
    game_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """标记游戏为不感兴趣（写入推荐历史以降低未来推荐权重）"""
    from database import RecommendationHistory
    existing = db.query(RecommendationHistory).filter(
        RecommendationHistory.user_id == current_user.id,
        RecommendationHistory.game_id == game_id,
    ).first()
    if not existing:
        db.add(RecommendationHistory(user_id=current_user.id, game_id=game_id))
        db.commit()
    return {"status": "ok"}


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
                description=_sanitize_html(game.description or ""),
                image_url=game.image_url or "",
                image_large=game.image_large or game.image_url or "",
                fallback_image=game.fallback_image or "",
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
                    name_cn=sg.name_cn or "", description=_sanitize_html(sg.description or ""),
                    image_url=sg.image_url or "",
                    image_large=sg.image_large or sg.image_url or "",
                    fallback_image=sg.fallback_image or "",
                    price=sg.price or "",
                    tags=[t.name for t in sg.tags],
                ))
    except: pass

    return {
        "id": game.id, "steam_app_id": game.steam_app_id,
        "name": game.name, "name_cn": game.name_cn or "",
        "description": _sanitize_html(game.description or ""),
        "image_url": game.image_url or "",
        "image_large": game.image_large or game.image_url or "",
        "fallback_image": game.fallback_image or "",
        "price": game.price or "",
        "release_date": game.release_date or "",
        "tags": [t.name for t in game.tags],
        "screenshots": screenshots,
        "review_positive": review_positive,
        "review_total": review_total,
        "user_reviews": json.loads(game.user_reviews or "[]"),
        "similar_games": similar,
    }
