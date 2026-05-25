import json
import urllib.request
import logging
from config import LLM_ENABLED, LLM_API_BASE, LLM_API_KEY

CHAT_MODEL = "deepseek-chat"  # 标签/名称提取用 chat 模型，不用 reasoning 模型

logger = logging.getLogger(__name__)

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LLM_API_KEY}",
}

def _is_available() -> bool:
    return LLM_ENABLED and bool(LLM_API_KEY)

def _chat(messages: list[dict], max_tokens: int = 300) -> str:
    if not _is_available():
        return ""
    try:
        body = json.dumps({
            "model": CHAT_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(f"{LLM_API_BASE}/chat/completions", data=body, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        return (msg.get("content", "") or "").strip()
    except Exception as e:
        logger.warning(f"LLM chat failed: {e}")
        return ""

def extract_tags(description: str) -> list[str]:
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
    if not en_name:
        return ""
    result = _chat([
        {"role": "system", "content": "你是一个游戏本地化专家。根据英文游戏名和描述，生成一个简洁的中文名（不超过15字）。只返回中文名，不要解释。"},
        {"role": "user", "content": f"游戏名: {en_name}\n描述: {description[:1000]}"},
    ], max_tokens=30)
    return result[:30] if result else ""

def get_embedding(text: str) -> list[float]:
    return []

def embedding_available() -> bool:
    return False
