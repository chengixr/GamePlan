from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import Game, Rating
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
