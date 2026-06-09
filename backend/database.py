from sqlalchemy import create_engine, event, Column, Integer, String, Text, DateTime, Date, Boolean, Float, ForeignKey, Table, UniqueConstraint
from sqlalchemy.orm import declarative_base, relationship, sessionmaker
from datetime import datetime, timezone
from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30})

@event.listens_for(engine, "connect")
def _set_wal(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

game_tag_assoc = Table(
    "game_tags", Base.metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("game_id", Integer, ForeignKey("games.id"), nullable=False),
    Column("tag_id", Integer, ForeignKey("tags.id"), nullable=False),
    UniqueConstraint("game_id", "tag_id"),
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    nickname = Column(String(50), default="")
    password_hash = Column(String(128), nullable=False)
    is_admin = Column(Boolean, default=False)
    avatar = Column(String(10), default="1")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Game(Base):
    __tablename__ = "games"
    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_app_id = Column(Integer, unique=True, nullable=False)
    name = Column(String(256), nullable=False)
    name_cn = Column(String(256), default="")
    description = Column(Text, default="")
    image_url = Column(String(512), default="")
    image_large = Column(String(512), default="")
    fallback_image = Column(String(512), default="")
    price = Column(String(32), default="")
    release_date = Column(String(32), default="")
    screenshots = Column(Text, default="[]")
    review_summary = Column(Text, default="{}")
    reviews_synced_at = Column(DateTime, nullable=True)
    llm_tags_enriched = Column(Boolean, default=False)
    user_reviews = Column(Text, default="[]")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    tags = relationship("Tag", secondary=game_tag_assoc, back_populates="games")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    weight = Column(Float, default=1.0)
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

class GameEmbedding(Base):
    __tablename__ = "game_embeddings"
    game_id = Column(Integer, ForeignKey("games.id"), primary_key=True)
    embedding = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class Favorite(Base):
    __tablename__ = "favorites"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("user_id", "game_id"),)

class UserSession(Base):
    __tablename__ = "user_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)


class SteamRanking(Base):
    """每小时同步的 Steam 热销排名快照（仅排名和名称，不含详情）"""
    __tablename__ = "steam_rankings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    steam_app_id = Column(Integer, nullable=False, index=True)
    name = Column(String(256), nullable=False)
    rank = Column(Integer, nullable=False)
    snapshot_time = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

class DailyDiscovery(Base):
    """每日发现类游戏（new_releases / specials / coming_soon）"""
    __tablename__ = "daily_discovery"
    id = Column(Integer, primary_key=True, autoincrement=True)
    game_id = Column(Integer, ForeignKey("games.id"), nullable=False)
    category = Column(String(32), default="")
    date = Column(Date, nullable=False)
    snapshot_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))


def init_db():
    Base.metadata.create_all(bind=engine)
    _migrate_columns()


def _migrate_columns():
    """为已有数据库添加缺失的列和表"""
    from sqlalchemy import text, inspect
    inspector = inspect(engine)
    existing = {c['name'] for c in inspector.get_columns('games')}
    migrations = [
        ("image_large", "VARCHAR(512) DEFAULT ''"),
        ("fallback_image", "VARCHAR(512) DEFAULT ''"),
    ]
    with engine.connect() as conn:
        for col_name, col_def in migrations:
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE games ADD COLUMN {col_name} {col_def}"))
        conn.commit()
