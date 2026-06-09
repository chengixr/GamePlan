from datetime import date, datetime, timedelta
import json
import random
import threading
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select as sa_select
from database import Rating, Game, DailyTopSeller, Favorite, RecommendationHistory
from tag_library import get_tag_weight

# game-tag 映射缓存（5 分钟 TTL）
_tag_cache = {}
_tag_cache_lock = threading.Lock()

def _get_game_tag_sets(db: Session) -> dict[int, dict[str, float]]:
    """返回 {game_id: {tag_name: weight}} 加权标签映射"""
    now = datetime.now()
    with _tag_cache_lock:
        if _tag_cache.get("expires", now) > now:
            return _tag_cache["data"]
    game_tag_sets = {}
    for g in db.query(Game).options(joinedload(Game.tags)).all():
        game_tag_sets[g.id] = {t.name: get_tag_weight(t.name) for t in g.tags}
    with _tag_cache_lock:
        _tag_cache["data"] = game_tag_sets
        _tag_cache["expires"] = now + timedelta(minutes=5)
    return game_tag_sets


def _weighted_jaccard(tags_a: dict[str, float], tags_b: dict[str, float]) -> float:
    """加权 Jaccard 相似度"""
    common = set(tags_a.keys()) & set(tags_b.keys())
    all_keys = set(tags_a.keys()) | set(tags_b.keys())
    if not all_keys:
        return 0.0
    inter_w = sum(min(tags_a[k], tags_b[k]) for k in common)
    union_w = sum(max(tags_a.get(k, 0), tags_b.get(k, 0)) for k in all_keys)
    return inter_w / union_w if union_w > 0 else 0.0


# 推荐结果缓存（5 分钟 TTL，按用户隔离）
_rec_cache = {}
_rec_cache_lock = threading.Lock()

def clear_recommender_cache():
    """同步后清除缓存"""
    global _tag_cache, _rec_cache
    with _tag_cache_lock:
        _tag_cache.clear()
    with _rec_cache_lock:
        _rec_cache.clear()


def _excluded_ids(db: Session, user_id: int) -> tuple[set[int], set[int]]:
    """返回 (已评分, 已收藏) 的游戏 ID 集合"""
    rated = {r[0] for r in db.query(Rating.game_id).filter(Rating.user_id == user_id).all()}
    faved = {f[0] for f in db.query(Favorite.game_id).filter(Favorite.user_id == user_id).all()}
    return rated, faved


def _get_rec_history(db: Session, user_id: int) -> set[int]:
    """返回已被推荐过的游戏 ID 集合"""
    rows = db.query(RecommendationHistory.game_id).filter(
        RecommendationHistory.user_id == user_id
    ).all()
    return {r[0] for r in rows}


def _freshness_boost(db: Session) -> dict[int, float]:
    """新入库游戏（7 天内）获得小幅加成，越新加成越高"""
    cutoff = datetime.now() - timedelta(days=7)
    recent = db.query(Game.id, Game.created_at).filter(Game.created_at >= cutoff).all()
    boost = {}
    for gid, created in recent:
        days_old = max(1, (datetime.now() - created).days)
        boost[gid] = 0.12 * (7 - days_old) / 7  # 当天 0.12，7 天衰减到 0
    return boost


def get_recommendations(db: Session, user_id: int) -> tuple[int, list[int]]:
    rated_ids, faved_ids = _excluded_ids(db, user_id)
    exclude_ids = rated_ids | faved_ids
    rating_count = len(rated_ids)
    rec_history = _get_rec_history(db, user_id)

    # 推荐结果缓存（5 分钟）：避免同步期间重复计算超时
    cache_key = f"rec_{user_id}_{rating_count}_{len(faved_ids)}"
    with _rec_cache_lock:
        entry = _rec_cache.get(cache_key)
        if entry and entry["expires"] > datetime.now():
            return entry["total"], entry["ids"]

    # 冷启动：过滤已评分 + 已收藏，加入随机（不以日期为种子，每次不同）
    if rating_count < 5:
        today = date.today()
        sellers = (
            db.query(DailyTopSeller)
            .filter(DailyTopSeller.date == today)
            .order_by(DailyTopSeller.rank)
            .limit(100)
            .all()
        )
        game_ids = [s.game_id for s in sellers if s.game_id not in exclude_ids]
        random.shuffle(game_ids)
        # 历史推荐过且不足 20 款时保留，否则优先未推荐的
        unseen = [gid for gid in game_ids if gid not in rec_history]
        seen = [gid for gid in game_ids if gid in rec_history]
        game_ids = (unseen + seen)[:20]
        result = (len(game_ids), game_ids)
        with _rec_cache_lock:
            _rec_cache[cache_key] = {"total": result[0], "ids": result[1], "expires": datetime.now() + timedelta(minutes=5)}
        return result

    game_tag_sets = _get_game_tag_sets(db)
    freshness = _freshness_boost(db)

    # 获取当前用户评分
    current_ratings = db.query(Rating).filter(Rating.user_id == user_id).all()
    current_scores = {r.game_id: r.score for r in current_ratings}
    rated_game_ids = set(current_scores.keys())

    # 协同过滤：只查询与当前用户有共同评分游戏的用户（大幅减少数据量）
    from sqlalchemy import distinct
    cf_user_ids = set()
    if rated_game_ids:
        cf_rows = db.query(distinct(Rating.user_id)).filter(
            Rating.game_id.in_(rated_game_ids),
            Rating.user_id != user_id,
        ).limit(200).all()
        cf_user_ids = {r[0] for r in cf_rows}

        # 获取相似用户的评分（仅高分 >= 4，减少数据量）
        cf_ratings = db.query(Rating).filter(
            Rating.user_id.in_(cf_user_ids),
            Rating.score >= 4,
        ).all()

        user_scores = {user_id: current_scores}
        for r in cf_ratings:
            user_scores.setdefault(r.user_id, {})[r.game_id] = r.score
    else:
        user_scores = {user_id: current_scores}

    # === 标签相似度（正向） ===
    high_rated = [gid for gid, s in current_scores.items() if s >= 4]
    low_rated = [gid for gid, s in current_scores.items() if s <= 2]

    # === Embedding 模式（LLM可用且覆盖率 > 50% 时启用） ===
    embedding_mode = False
    embeddings = {}
    try:
        from database import GameEmbedding
        from llm import embedding_available
        if embedding_available():
            for ge in db.query(GameEmbedding).all():
                try:
                    embeddings[ge.game_id] = json.loads(ge.embedding)
                except: pass
            coverage = len(embeddings) / max(1, len(game_tag_sets))
            if coverage > 0.5 and high_rated:
                embedding_mode = True
    except: pass

    if embedding_mode:
        profile_vec = None
        total_weight = 0
        for gid in high_rated:
            if gid in embeddings:
                vec = embeddings[gid]
                weight = current_scores[gid]
                if profile_vec is None:
                    profile_vec = [v * weight for v in vec]
                else:
                    profile_vec = [profile_vec[i] + vec[i] * weight for i in range(len(vec))]
                total_weight += weight

        if profile_vec and total_weight > 0:
            profile_vec = [v / total_weight for v in profile_vec]
            for gid in game_tag_sets:
                if gid in exclude_ids or gid not in embeddings:
                    continue
                tag_scores[gid] = _cosine_similarity_list(profile_vec, embeddings[gid])

    # 喜欢标签集（带权重累加，取最高权重）
    high_rated_tags = {}
    for gid in high_rated:
        for tag, w in game_tag_sets.get(gid, {}).items():
            high_rated_tags[tag] = max(high_rated_tags.get(tag, 0), w)

    # 不喜欢标签集
    low_rated_tags = {}
    for gid in low_rated:
        for tag, w in game_tag_sets.get(gid, {}).items():
            low_rated_tags[tag] = max(low_rated_tags.get(tag, 0), w)

    tag_scores = {}
    dislike_penalties = {}
    for gid, g_tags in game_tag_sets.items():
        if gid in exclude_ids:
            continue
        tag_scores[gid] = _weighted_jaccard(high_rated_tags, g_tags) if high_rated_tags else 0.0
        dislike_penalties[gid] = _weighted_jaccard(low_rated_tags, g_tags) if low_rated_tags else 0.0

    # === 协同过滤 ===
    cf_scores = {}
    other_users = [uid for uid in user_scores if uid != user_id]
    current_vec = _rating_vector(current_scores)

    if other_users and current_vec:
        similarities = []
        for ouid in other_users:
            other_vec = _rating_vector(user_scores[ouid])
            if not other_vec:
                continue
            sim = _cosine_similarity(current_vec, other_vec)
            similarities.append((ouid, sim))
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_similar = similarities[:10]

        cf_accum = {}
        for ouid, sim in top_similar:
            for gid, score in user_scores[ouid].items():
                if score >= 4 and gid not in exclude_ids:
                    cf_accum.setdefault(gid, []).append(sim)
        for gid, sims in cf_accum.items():
            cf_scores[gid] = sum(sims) / len(sims) if sims else 0.0

    # === 加载 Steam 评价数据 ===
    review_boost = {}
    all_games_reviews = db.query(Game.id, Game.review_summary).all()
    for gid, summary in all_games_reviews:
        try:
            rd = json.loads(summary or "{}")
            total = rd.get("total", 0)
            if total >= 50:
                review_boost[gid] = (rd.get("positive", 0) / total) * 0.15
        except:
            pass

    # === 混合打分 ===
    DISLIKE_PENALTY_WEIGHT = 0.3
    REC_HISTORY_PENALTY = 0.5  # 已推荐过 ×0.5
    FRESHNESS_WEIGHT = 1.0     # 新鲜度加成权重
    NOISE_SCALE = 0.03          # 随机扰动幅度

    rng = random.Random()
    final_scores = {}
    for gid in set(list(tag_scores.keys()) + list(cf_scores.keys())):
        score = tag_scores.get(gid, 0) * 0.6 + cf_scores.get(gid, 0) * 0.4
        penalty = dislike_penalties.get(gid, 0) * DISLIKE_PENALTY_WEIGHT
        score = max(0, score - penalty + review_boost.get(gid, 0))

        # 新鲜度加成
        score += freshness.get(gid, 0) * FRESHNESS_WEIGHT

        # 已推荐降权
        if gid in rec_history:
            score *= REC_HISTORY_PENALTY

        # 随机扰动（±3%），打破确定性排序
        score *= 1.0 + rng.uniform(-NOISE_SCALE, NOISE_SCALE)

        final_scores[gid] = max(0, score)

    sorted_games = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
    game_ids = [gid for gid, _ in sorted_games]

    # 保存到缓存
    result = (len(game_ids), game_ids)
    with _rec_cache_lock:
        _rec_cache[cache_key] = {"total": result[0], "ids": result[1], "expires": datetime.now() + timedelta(minutes=5)}
    return result


def get_similar_games(db: Session, game_id: int, limit: int = 6) -> list[int]:
    """基于标签 + 协同过滤返回相似游戏"""
    target_game = db.query(Game).filter(Game.id == game_id).first()
    if not target_game:
        return []

    target_tags = {t.name: get_tag_weight(t.name) for t in target_game.tags}
    all_games = db.query(Game).options(joinedload(Game.tags)).filter(Game.id != game_id).all()

    # 标签加权 Jaccard 相似度
    tag_scores = {}
    for g in all_games:
        g_tags = {t.name: get_tag_weight(t.name) for t in g.tags}
        tag_scores[g.id] = _weighted_jaccard(target_tags, g_tags)

    # 协同过滤：找到评分过当前游戏且高分的用户，看他们还喜欢什么
    cf_scores = {}
    similar_users_subq = sa_select(Rating.user_id).where(
        Rating.game_id == game_id, Rating.score >= 4
    ).scalar_subquery()
    liked_by = db.query(Rating.user_id, Rating.game_id, Rating.score).filter(
        Rating.user_id.in_(similar_users_subq)
    ).all()

    user_scores = {}
    for uid, gid, s in liked_by:
        user_scores.setdefault(uid, {})[gid] = s

    for uid, scores in user_scores.items():
        for gid, s in scores.items():
                if s >= 4 and gid != game_id:
                    cf_scores[gid] = cf_scores.get(gid, 0) + 1

    # 归一化协同分数
    max_cf = max(cf_scores.values()) if cf_scores else 1
    for gid in cf_scores:
        cf_scores[gid] = cf_scores[gid] / max_cf

    # Steam 评价加成
    review_boost_sim = {}
    for g in all_games:
        try:
            rd = json.loads(g.review_summary or "{}")
            total = rd.get("total", 0)
            if total >= 50:
                review_boost_sim[g.id] = (rd.get("positive", 0) / total) * 0.15
        except: pass

    # 混合
    final = {}
    for g in all_games:
        final[g.id] = tag_scores.get(g.id, 0) * 0.6 + cf_scores.get(g.id, 0) * 0.4 + review_boost_sim.get(g.id, 0)

    sorted_games = sorted(final.items(), key=lambda x: x[1], reverse=True)
    return [gid for gid, _ in sorted_games[:limit]]


def _cosine_similarity_list(a: list[float], b: list[float]) -> float:
    if not a or not b: return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(y ** 2 for y in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def _rating_vector(scores: dict[int, int]) -> dict[int, float] | None:
    if not scores:
        return None
    mean = sum(scores.values()) / len(scores)
    return {gid: s - mean for gid, s in scores.items()}


def _cosine_similarity(a: dict[int, float], b: dict[int, float]) -> float:
    common = set(a.keys()) & set(b.keys())
    if not common:
        return 0.0
    dot = sum(a[k] * b[k] for k in common)
    norm_a = sum(v ** 2 for v in a.values()) ** 0.5
    norm_b = sum(v ** 2 for v in b.values()) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
