from fastapi import APIRouter, HTTPException, Request, Response, Depends
from sqlalchemy.orm import Session
from passlib.hash import bcrypt
from datetime import datetime, timezone, timedelta
from database import SessionLocal, User, UserSession
from models import RegisterRequest, LoginRequest, UserResponse, UpdateProfileRequest, ChangePasswordRequest
import secrets
import logging

logger = logging.getLogger("auth")
router = APIRouter()

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

def _clean_expired_sessions(db: Session):
    db.query(UserSession).filter(UserSession.expires_at < datetime.now(timezone.utc)).delete()
    db.commit()

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="请先登录")
    sess = db.query(UserSession).filter(
        UserSession.session_id == session_id,
        UserSession.expires_at > datetime.now(timezone.utc)
    ).first()
    if not sess:
        raise HTTPException(status_code=401, detail="会话已过期，请重新登录")
    user = db.query(User).filter(User.id == sess.user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

def _create_session(db: Session, user_id: int) -> str:
    _clean_expired_sessions(db)
    session_id = secrets.token_hex(32)
    expires = datetime.now(timezone.utc) + timedelta(days=7)
    db.add(UserSession(session_id=session_id, user_id=user_id, expires_at=expires))
    db.commit()
    return session_id

def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id, username=user.username,
        nickname=user.nickname or user.username,
        avatar=user.avatar or "1"
    )

@router.post("/register", response_model=UserResponse)
def register(body: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        logger.warning(f"注册失败: 用户名 {body.username} 已存在")
        raise HTTPException(status_code=400, detail="该账号已被注册")
    user = User(username=body.username, nickname=body.username, password_hash=bcrypt.hash(body.password))
    db.add(user); db.commit(); db.refresh(user)
    logger.info(f"新用户注册: {user.username} (id={user.id})")
    session_id = _create_session(db, user.id)
    response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=7*24*3600, samesite="lax")
    return _user_response(user)

@router.post("/login", response_model=UserResponse)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not bcrypt.verify(body.password, user.password_hash):
        logger.warning(f"登录失败: 用户 {body.username} 密码错误或不存在")
        raise HTTPException(status_code=401, detail="账号或密码不正确")
    db.query(UserSession).filter(UserSession.user_id == user.id).delete()
    logger.info(f"用户登录: {user.username} (id={user.id})")
    session_id = _create_session(db, user.id)
    response.set_cookie(key="session_id", value=session_id, httponly=True, max_age=7*24*3600, samesite="lax")
    return _user_response(user)

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    session_id = request.cookies.get("session_id")
    if session_id:
        db.query(UserSession).filter(UserSession.session_id == session_id).delete()
        db.commit()
    logger.info(f"用户登出: {current_user.username} (id={current_user.id})")
    response.delete_cookie("session_id")
    return {"status": "ok"}

@router.put("/profile", response_model=UserResponse)
def update_profile(body: UpdateProfileRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if body.nickname is not None:
        if not body.nickname.strip():
            raise HTTPException(status_code=400, detail="昵称不能为空")
        current_user.nickname = body.nickname.strip()
    if body.avatar:
        if body.avatar not in [str(i) for i in range(1, 11)]:
            raise HTTPException(status_code=400, detail="无效的头像ID")
        current_user.avatar = body.avatar
    db.commit(); db.refresh(current_user)
    return _user_response(current_user)

@router.put("/password")
def change_password(body: ChangePasswordRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not bcrypt.verify(body.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="当前密码不正确")
    current_user.password_hash = bcrypt.hash(body.new_password)
    db.commit()
    return {"status": "ok"}

@router.get("/me", response_model=UserResponse)
def me(current_user: User = Depends(get_current_user)):
    return _user_response(current_user)
