import json
import time
import urllib.request
import logging
from config import LLM_ENABLED, LLM_API_BASE, LLM_API_KEY

CHAT_MODEL = "deepseek-chat"  # 标签/名称提取用 chat 模型，不用 reasoning 模型

logger = logging.getLogger(__name__)

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {LLM_API_KEY}",
}

# 熔断器状态
_CONSECUTIVE_FAILURES = 0
_CIRCUIT_OPEN_UNTIL = 0.0  # 熔断打开期间的时间戳阈值
CIRCUIT_BREAK_THRESHOLD = 5        # 连续失败 N 次后熔断
CIRCUIT_COOLDOWN_SECONDS = 1800    # 熔断冷却 30 分钟
_CIRCUIT_402_COOLDOWN_SECONDS = 7200  # 402 余额不足冷却 2 小时

def _is_available() -> bool:
    return LLM_ENABLED and bool(LLM_API_KEY)

def _circuit_is_open() -> bool:
    """熔断是否打开（阻止请求）"""
    return time.time() < _CIRCUIT_OPEN_UNTIL

def _chat(messages: list[dict], max_tokens: int = 300) -> str:
    global _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL

    if not _is_available():
        return ""
    if _circuit_is_open():
        remaining = int(_CIRCUIT_OPEN_UNTIL - time.time())
        logger.debug(f"LLM circuit open, {remaining}s remaining")
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
        # 成功则重置熔断
        _CONSECUTIVE_FAILURES = 0
        _CIRCUIT_OPEN_UNTIL = 0.0
        return (msg.get("content", "") or "").strip()
    except Exception as e:
        _CONSECUTIVE_FAILURES += 1
        err_msg = str(e)
        # 402 余额不足用更长的冷却时间
        is_402 = "402" in err_msg
        cooldown = _CIRCUIT_402_COOLDOWN_SECONDS if is_402 else CIRCUIT_COOLDOWN_SECONDS

        if _CONSECUTIVE_FAILURES >= CIRCUIT_BREAK_THRESHOLD:
            _CIRCUIT_OPEN_UNTIL = time.time() + cooldown
            logger.warning(
                f"LLM circuit OPEN (cooldown {cooldown}s) after {_CONSECUTIVE_FAILURES} consecutive failures"
            )
        logger.warning(f"LLM chat failed (fail #{_CONSECUTIVE_FAILURES}): {e}")
        return ""

def extract_tags(description: str) -> list[str]:
    if not description or len(description) < 20:
        return []
    from tag_library import build_prompt_section
    tag_list = build_prompt_section()
    text = description[:2000]
    result = _chat([
        {"role": "system", "content": f"你是一个游戏标签专家。根据游戏描述，从以下标签库中选择5-10个最匹配的中文标签，用逗号分隔。\n\n可用标签：{tag_list}\n\n规则：\n1. 只从标签库中选择，不要自创标签\n2. 选择与游戏最相关的标签\n3. 只返回标签，用逗号分隔，不要解释"},
        {"role": "user", "content": text},
    ], max_tokens=100)
    if not result:
        return []
    from tag_library import TAG_LIBRARY_SORTED
    raw_tags = [t.strip() for t in result.split(",") if t.strip()]
    # 过滤：只保留标签库中存在的
    valid = [t for t in raw_tags if t in TAG_LIBRARY_SORTED]
    return valid[:10] if valid else raw_tags[:10]

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
