from datetime import date
import random
from sqlalchemy.orm import Session
from database import Rating, Game, DailyTopSeller, RecommendationHistory

def get_recommendations(db: Session, user_id: int) -> tuple[int, list[int]]:
    rating_count = db.query(Rating).filter(Rating.user_id == user_id).count()

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
        return len(game_ids), game_ids

    all_ratings = db.query(Rating).all()
    user_scores = {}
    for r in all_ratings:
        user_scores.setdefault(r.user_id, {})[r.game_id] = r.score

    current_scores = user_scores.get(user_id, {})
    rated_game_ids = set(current_scores.keys())

    # === 标签相似度（正向） ===
    high_rated = [gid for gid, s in current_scores.items() if s >= 4]
    low_rated = [gid for gid, s in current_scores.items() if s <= 2]

    all_games = db.query(Game).all()
    game_tag_sets = {}
    for g in all_games:
        game_tag_sets[g.id] = {t.name for t in g.tags}

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
    for g in all_games:
        if g.id in rated_game_ids:
            continue
        g_tags = game_tag_sets.get(g.id, set())
        # 正向：与喜欢标签的 Jaccard 相似度
        if high_rated_tags and g_tags:
            inter = len(high_rated_tags & g_tags)
            union = len(high_rated_tags | g_tags)
            tag_scores[g.id] = inter / union if union > 0 else 0.0
        else:
            tag_scores[g.id] = 0.0
        # 负向：与不喜欢标签的 Jaccard 惩罚
        if low_rated_tags and g_tags:
            inter = len(low_rated_tags & g_tags)
            union = len(low_rated_tags | g_tags)
            dislike_penalties[g.id] = inter / union if union > 0 else 0.0

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

    # === 混合打分（含不喜欢降权） ===
    DISLIKE_PENALTY_WEIGHT = 0.3
    final_scores = {}
    for gid in set(list(tag_scores.keys()) + list(cf_scores.keys())):
        score = tag_scores.get(gid, 0) * 0.6 + cf_scores.get(gid, 0) * 0.4
        penalty = dislike_penalties.get(gid, 0) * DISLIKE_PENALTY_WEIGHT
        final_scores[gid] = max(0, score - penalty)

    # === 去重与降权 ===
    history = db.query(RecommendationHistory).filter(
        RecommendationHistory.user_id == user_id
    ).all()
    history_game_ids = {h.game_id for h in history}

    for gid in list(final_scores.keys()):
        if gid in history_game_ids:
            final_scores[gid] *= 0.5

    sorted_games = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
    game_ids = [gid for gid, _ in sorted_games if gid not in rated_game_ids]

    return len(game_ids), game_ids


def get_similar_games(db: Session, game_id: int, limit: int = 6) -> list[int]:
    """基于标签 + 协同过滤返回相似游戏"""
    target_game = db.query(Game).filter(Game.id == game_id).first()
    if not target_game:
        return []

    target_tags = {t.name for t in target_game.tags}
    all_games = db.query(Game).filter(Game.id != game_id).all()

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

    # 混合
    final = {}
    for g in all_games:
        final[g.id] = tag_scores.get(g.id, 0) * 0.6 + cf_scores.get(g.id, 0) * 0.4

    sorted_games = sorted(final.items(), key=lambda x: x[1], reverse=True)
    return [gid for gid, _ in sorted_games[:limit]]


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
