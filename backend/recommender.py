from datetime import date, datetime, timedelta
import json
import random
import threading
from sqlalchemy.orm import Session, joinedload
from database import Rating, Game, DailyTopSeller

# game-tag 映射缓存（5 分钟 TTL）
_tag_cache = {}
_tag_cache_lock = threading.Lock()

def _get_game_tag_sets(db: Session) -> dict[int, set[str]]:
    now = datetime.now()
    with _tag_cache_lock:
        if _tag_cache.get("expires", now) > now:
            return _tag_cache["data"]
    game_tag_sets = {}
    for g in db.query(Game).options(joinedload(Game.tags)).all():
        game_tag_sets[g.id] = {t.name for t in g.tags}
    with _tag_cache_lock:
        _tag_cache["data"] = game_tag_sets
        _tag_cache["expires"] = now + timedelta(minutes=5)
    return game_tag_sets


# 推荐结果缓存（5 分钟 TTL，按用户隔离）
_rec_cache = {}
_rec_cache_lock = threading.Lock()

# 评分数据缓存（2 分钟，减少同步期间的 DB 压力）
_ratings_cache = {}
_ratings_cache_lock = threading.Lock()

def clear_recommender_cache():
    """同步后清除缓存"""
    global _tag_cache, _rec_cache, _ratings_cache
    with _tag_cache_lock:
        _tag_cache.clear()
    with _rec_cache_lock:
        _rec_cache.clear()
    with _ratings_cache_lock:
        _ratings_cache.clear()


def get_recommendations(db: Session, user_id: int) -> tuple[int, list[int]]:
    rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()

    # 推荐结果缓存（5 分钟）：避免同步期间重复计算超时
    cache_key = f"rec_{user_id}_{rating_count}"
    with _rec_cache_lock:
        entry = _rec_cache.get(cache_key)
        if entry and entry["expires"] > datetime.now():
            return entry["total"], entry["ids"]

    # 冷启动：用 user_id + 日期做种子，保证同日同用户分页稳定
    if rating_count < 5:
        today = date.today()
        sellers = (
            db.query(DailyTopSeller)
            .filter(DailyTopSeller.date == today)
            .order_by(DailyTopSeller.rank)
            .limit(100)
            .all()
        )
        game_ids = [s.game_id for s in sellers]
        rng = random.Random(f"{user_id}-{today.isoformat()}")
        rng.shuffle(game_ids)
        game_ids = game_ids[:20]
        result = (len(game_ids), game_ids)
        with _rec_cache_lock:
            _rec_cache[cache_key] = {"total": result[0], "ids": result[1], "expires": datetime.now() + timedelta(minutes=5)}
        return result

    # 评分数据缓存读取（存储原始元组避免 DetachedInstanceError）
    now = datetime.now()
    with _ratings_cache_lock:
        if _ratings_cache.get("expires", now) > now:
            rating_rows = _ratings_cache["data"]
        else:
            rating_rows = [(r.user_id, r.game_id, r.score) for r in db.query(Rating).all()]
            _ratings_cache["data"] = rating_rows
            _ratings_cache["expires"] = now + timedelta(minutes=2)

    user_scores = {}
    for uid, gid, score in rating_rows:
        user_scores.setdefault(uid, {})[gid] = score

    current_scores = user_scores.get(user_id, {})
    rated_game_ids = set(current_scores.keys())

    # === 标签相似度（正向） ===
    high_rated = [gid for gid, s in current_scores.items() if s >= 4]
    low_rated = [gid for gid, s in current_scores.items() if s <= 2]

    game_tag_sets = _get_game_tag_sets(db)

    # === Embedding 模式（LLM可用且覆盖率 > 50% 时启用） ===
    embedding_mode = False
    embeddings = {}
    try:
        from database import GameEmbedding
        from llm import embedding_available
        if embedding_available():
            # 加载所有 embedding
            for ge in db.query(GameEmbedding).all():
                try:
                    embeddings[ge.game_id] = json.loads(ge.embedding)
                except: pass
            coverage = len(embeddings) / max(1, len(game_tag_sets))
            if coverage > 0.5 and high_rated:
                embedding_mode = True
    except: pass

    if embedding_mode:
        # 用户画像向量 = 高分游戏向量的加权平均
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
            # 用 embedding 相似度替换标签相似度
            for gid in game_tag_sets:
                if gid in rated_game_ids or gid not in embeddings:
                    continue
                tag_scores[gid] = _cosine_similarity_list(profile_vec, embeddings[gid])

    # 喜欢标签集
    high_rated_tags = set()
    for gid in high_rated:
        high_rated_tags |= game_tag_sets.get(gid, set())

    # 不喜欢标签集
    low_rated_tags = set()
    for gid in low_rated:
        low_rated_tags |= game_tag_sets.get(gid, set())

    tag_scores = {}
    dislike_penalties = {}
    for gid, g_tags in game_tag_sets.items():
        if gid in rated_game_ids:
            continue
        # 正向：与喜欢标签的 Jaccard 相似度
        if high_rated_tags and g_tags:
            inter = len(high_rated_tags & g_tags)
            union = len(high_rated_tags | g_tags)
            tag_scores[gid] = inter / union if union > 0 else 0.0
        else:
            tag_scores[gid] = 0.0
        # 负向：与不喜欢标签的 Jaccard 惩罚
        if low_rated_tags and g_tags:
            inter = len(low_rated_tags & g_tags)
            union = len(low_rated_tags | g_tags)
            dislike_penalties[gid] = inter / union if union > 0 else 0.0

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
                if score >= 4 and gid not in rated_game_ids:
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
            if total >= 50:  # 至少 50 条评价才计入
                review_boost[gid] = (rd.get("positive", 0) / total) * 0.15
        except:
            pass

    # === 混合打分（含不喜欢降权 + Steam 评价加成） ===
    DISLIKE_PENALTY_WEIGHT = 0.3
    final_scores = {}
    for gid in set(list(tag_scores.keys()) + list(cf_scores.keys())):
        score = tag_scores.get(gid, 0) * 0.6 + cf_scores.get(gid, 0) * 0.4
        penalty = dislike_penalties.get(gid, 0) * DISLIKE_PENALTY_WEIGHT
        final_scores[gid] = max(0, score - penalty + review_boost.get(gid, 0))

    # === 去除已打分 ===
    sorted_games = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
    game_ids = [gid for gid, _ in sorted_games if gid not in rated_game_ids]

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

    target_tags = {t.name for t in target_game.tags}
    all_games = db.query(Game).options(joinedload(Game.tags)).filter(Game.id != game_id).all()

    # 标签 Jaccard 相似度
    tag_scores = {}
    for g in all_games:
        g_tags = {t.name for t in g.tags}
        if not target_tags or not g_tags:
            tag_scores[g.id] = 0.0
        else:
            inter = len(target_tags & g_tags)
            union = len(target_tags | g_tags)
            tag_scores[g.id] = inter / union if union > 0 else 0.0

    # 协同过滤：找到评分过当前游戏的用户，看他们还喜欢什么
    all_ratings = db.query(Rating).all()
    user_scores = {}
    for r in all_ratings:
        user_scores.setdefault(r.user_id, {})[r.game_id] = r.score

    cf_scores = {}
    for uid, scores in user_scores.items():
        if game_id in scores and scores[game_id] >= 4:
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
