from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from datetime import date
import json
from database import SessionLocal, Game, DailyTopSeller, RecommendationHistory, Tag
from models import GameResponse, PaginatedResponse
from auth import get_current_user, get_db
from recommender import get_recommendations

router = APIRouter()

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
                name_cn=game.name_cn or "",
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
    # 仅在首页时批量写入推荐历史，避免污染后续分页的排序
    if page == 1:
        for gid in game_ids:
            db.add(RecommendationHistory(user_id=current_user.id, game_id=gid))
        db.commit()
    start = (page - 1) * page_size
    paged_ids = game_ids[start : start + page_size]
    items = []
    for gid in paged_ids:
        game = db.query(Game).options(joinedload(Game.tags)).filter(Game.id == gid).first()
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
