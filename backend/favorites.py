from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
import json
from database import Game, Favorite
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
