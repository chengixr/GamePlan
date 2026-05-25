# LLM 集成（DeepSeek） - 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 接入 DeepSeek 大模型实现标签提取、中文名生成、Embedding 推荐引擎，所有功能带降级方案。

**Architecture:** 新增 `backend/llm.py` 客户端模块，更新 config 支持 API Key，`game_embeddings` 表存储向量，推荐引擎自动切换 LLM/标签模式。

**Tech Stack:** Python requests + DeepSeek API (OpenAI 兼容)

---

### Task 1: 配置层

**Files:**
- Modify: `config/config.json`
- Modify: `backend/config.py`

- [ ] **Step 1: 更新 config.json**

添加 LLM 配置块：
```json
  "llm": {
    "api_base": "https://api.deepseek.com/v1",
    "api_key": "",
    "model": "deepseek-chat",
    "embedding_model": "deepseek-embed",
    "enabled": true
  }
```

- [ ] **Step 2: 更新 config.py**

添加读取 LLM 配置：
```python
_llm = _cfg.get("llm", {})
LLM_ENABLED = os.environ.get("LLM_ENABLED", str(_llm.get("enabled", False))).lower() == "true"
LLM_API_BASE = os.environ.get("DEEPSEEK_API_BASE", _llm.get("api_base", "https://api.deepseek.com/v1"))
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", _llm.get("api_key", ""))
LLM_MODEL = os.environ.get("DEEPSEEK_MODEL", _llm.get("model", "deepseek-chat"))
LLM_EMBEDDING_MODEL = os.environ.get("DEEPSEEK_EMBEDDING", _llm.get("embedding_model", "deepseek-embed"))
```

- [ ] **Step 3: 验证**

```bash
python3 -c "from config import LLM_ENABLED, LLM_API_BASE; print(f'enabled={LLM_ENABLED}, base={LLM_API_BASE}')"
```

---

### Task 2: LLM 客户端

**Files:**
- Create: `backend/llm.py`

- [ ] **Step 1: 创建 llm.py**

```python
import json
import urllib.request
import logging
from config import LLM_ENABLED, LLM_API_BASE, LLM_API_KEY, LLM_MODEL, LLM_EMBEDDING_MODEL

logger = logging.getLogger(__name__)

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LLM_API_KEY}",
}

def _is_available() -> bool:
    return LLM_ENABLED and bool(LLM_API_KEY)

def _chat(messages: list[dict], max_tokens: int = 300) -> str:
    """发送聊天请求，失败返回空字符串"""
    if not _is_available():
        return ""
    try:
        body = json.dumps({
            "model": LLM_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(f"{LLM_API_BASE}/chat/completions", data=body, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"LLM chat 失败: {e}")
        return ""

def extract_tags(description: str) -> list[str]:
    """从游戏描述提取 5-10 个中文标签"""
    if not description or len(description) < 20:
        return []
    text = description[:2000]
    result = _chat([
        {"role": "system", "content": "你是一个游戏标签专家。根据游戏描述，提取5-10个中文标签，用逗号分隔。只返回标签，不要解释。"},
        {"role": "user", "content": text},
    ], max_tokens=100)
    if not result:
        return []
    return [t.strip() for t in result.split(",") if t.strip()][:10]

def generate_chinese_name(en_name: str, description: str) -> str:
    """生成中文游戏名"""
    if not en_name:
        return ""
    result = _chat([
        {"role": "system", "content": "你是一个游戏本地化专家。根据英文游戏名和描述，生成一个简洁的中文名（不超过15字）。只返回中文名，不要解释。"},
        {"role": "user", "content": f"游戏名: {en_name}\n描述: {description[:1000]}"},
    ], max_tokens=30)
    return result[:30] if result else ""

def get_embedding(text: str) -> list[float]:
    """获取文本的 embedding 向量"""
    if not _is_available() or not text:
        return []
    try:
        body = json.dumps({
            "model": LLM_EMBEDDING_MODEL,
            "input": text[:8000],
        }).encode()
        req = urllib.request.Request(f"{LLM_API_BASE}/embeddings", data=body, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=30)
        data = json.loads(resp.read())
        return data["data"][0]["embedding"]
    except Exception as e:
        logger.warning(f"Embedding 失败: {e}")
        return []

def batch_embeddings(texts: list[str]) -> list[list[float]]:
    """批量 embedding，逐个请求"""
    results = []
    for text in texts:
        emb = get_embedding(text)
        results.append(emb)
    return results

def embedding_available() -> bool:
    """检查 embedding 是否可用"""
    return _is_available()
```

- [ ] **Step 2: 验证**

```bash
python3 -c "
from llm import extract_tags, generate_chinese_name, get_embedding, embedding_available
print(f'available: {embedding_available()}')
if embedding_available():
    print(f'tags: {extract_tags(\"An open world action RPG with crafting and survival elements\")}')
    print(f'name: {generate_chinese_name(\"Elden Ring\", \"An action RPG set in a dark fantasy world\")}')
    emb = get_embedding('test')
    print(f'embedding dims: {len(emb)}')
else:
    print('LLM not configured, all should return empty/default')
    print(f'tags: {extract_tags(\"test\")}')  # should be []
    print(f'name: {generate_chinese_name(\"test\", \"desc\")}')  # should be ''
    print(f'embedding: {get_embedding(\"test\")}')  # should be []
"
```

---

### Task 3: 数据库新增 game_embeddings 表

**Files:**
- Modify: `backend/database.py`

- [ ] **Step 1: 添加模型**

在 `RecommendationHistory` 类之后添加：
```python
class GameEmbedding(Base):
    __tablename__ = "game_embeddings"
    game_id = Column(Integer, ForeignKey("games.id"), primary_key=True)
    embedding = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 2: 运行迁移**

```bash
sqlite3 /chenghao/claudeProject/GamePlan/backend/gameplan.db "CREATE TABLE IF NOT EXISTS game_embeddings (game_id INTEGER PRIMARY KEY REFERENCES games(id), embedding TEXT NOT NULL, updated_at DATETIME);"
```

- [ ] **Step 3: 验证**

```bash
sqlite3 /chenghao/claudeProject/GamePlan/backend/gameplan.db ".schema game_embeddings"
```

---

### Task 4: 同步中调用 LLM

**Files:**
- Modify: `backend/steam_sync.py`

- [ ] **Step 1: 在 `_try_fetch_details` 中使用 LLM 标签**

在现有标签获取后追加 LLM 标签：
```python
        # LLM 标签补充
        desc_for_llm = gd.get("detailed_description", "") or gd.get("short_description", "")
        if desc_for_llm:
            from llm import extract_tags
            llm_tags = extract_tags(desc_for_llm)
            for t in llm_tags:
                if t not in tags:
                    tags.append(t)
```

- [ ] **Step 2: LLM 中文名优先**

```python
        name_cn = gd.get("name", "")
        # LLM 生成中文名（优先于 Steam 官方中文名）
        if not name_cn or name_cn == gd.get("name", ""):
            from llm import generate_chinese_name
            llm_cn = generate_chinese_name(
                gd.get("name", ""),
                gd.get("short_description", "") or gd.get("detailed_description", "")
            )
            if llm_cn:
                name_cn = llm_cn
```

---

### Task 5: Embedding 构建 + 推荐引擎更新

**Files:**
- Create/Modify: `backend/recommender.py`
- Modify: `backend/main.py`

- [ ] **Step 1: 添加 embedding 构建接口**

在 `main.py` 中添加：
```python
@app.post("/api/llm/build-embeddings")
def build_embeddings():
    """为无 embedding 的游戏批量构建 embedding"""
    from llm import get_embedding, embedding_available
    from database import SessionLocal, Game, GameEmbedding
    import json

    if not embedding_available():
        return {"status": "unavailable", "message": "LLM 未配置或不可用"}

    db = SessionLocal()
    try:
        games = db.query(Game).outerjoin(GameEmbedding).filter(GameEmbedding.game_id == None).all()
        built = 0
        for g in games:
            desc = (g.description or "")[:2000]
            if len(desc) < 50:
                continue
            emb = get_embedding(desc)
            if emb:
                db.merge(GameEmbedding(game_id=g.id, embedding=json.dumps(emb)))
                built += 1
                if built % 10 == 0:
                    db.commit()
        db.commit()
        return {"status": "ok", "built": built, "total": len(games)}
    finally:
        db.close()
```

- [ ] **Step 2: 更新推荐引擎**

在 `recommender.py` 的混合打分前，尝试使用 embedding 模式：
```python
    # 尝试 embedding 模式
    embedding_mode = False
    try:
        from database import GameEmbedding
        from llm import embedding_available
        embedding_mode = embedding_available()
    except: pass

    if embedding_mode:
        # 获取所有游戏的 embedding
        embeddings = {}
        for g in all_games:
            ge = db.query(GameEmbedding).filter(GameEmbedding.game_id == g.id).first()
            if ge:
                try:
                    embeddings[g.id] = json.loads(ge.embedding)
                except: pass

        # 覆盖率 > 50% 才启用
        coverage = len(embeddings) / max(1, len(all_games))
        if coverage > 0.5 and high_rated:
            # 构建用户画像向量（高分游戏向量的加权平均）
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

                # 用 embedding 相似度替代标签相似度
                for g in all_games:
                    if g.id in rated_game_ids or g.id not in embeddings:
                        continue
                    sim = _cosine_similarity_dict(profile_vec, embeddings[g.id])
                    tag_scores[g.id] = sim  # 替换标签分数

    # 然后继续原有的混合打分逻辑（tag_scores 可能已被 embedding 替换）
    ...
```

添加 `_cosine_similarity_dict` 辅助函数：
```python
def _cosine_similarity_dict(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x ** 2 for x in a) ** 0.5
    norm_b = sum(y ** 2 for y in b) ** 0.5
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
```

- [ ] **Step 3: 验证**

```bash
# 检查 embedding 是否可用
curl -s -X POST http://127.0.0.1:8000/api/llm/build-embeddings

# 验证推荐（自动降级/启用）
curl -s -b /tmp/cookies.txt http://127.0.0.1:8000/api/games/recommended?page=1&page_size=3 | python3 -c "import json,sys; d=json.load(sys.stdin); print(f'total={d[\"total\"]}')"
```

---

## 验证清单

```bash
# 1. LLM 可用性
python3 -c "from llm import embedding_available; print(embedding_available())"

# 2. 标签提取
python3 -c "from llm import extract_tags; print(extract_tags('A sci-fi FPS game with RPG elements'))"

# 3. 中文名生成
python3 -c "from llm import generate_chinese_name; print(generate_chinese_name('Elden Ring', 'Dark fantasy action RPG'))"

# 4. Embedding 构建
curl -s -X POST http://127.0.0.1:8000/api/llm/build-embeddings

# 5. 推荐引擎
curl -s -b /tmp/cookies.txt http://127.0.0.1:8000/api/games/recommended?page=1&page_size=3

# 6. 前端构建
cd frontend && npm run build
```
