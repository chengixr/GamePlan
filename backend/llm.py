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

def _chat(messages: list[dict], max_tokens: int = 300, caller: str = "") -> str:
    global _CONSECUTIVE_FAILURES, _CIRCUIT_OPEN_UNTIL

    if not _is_available():
        logger.info(f"{caller} skipped (LLM disabled)")
        return ""
    if _circuit_is_open():
        remaining = int(_CIRCUIT_OPEN_UNTIL - time.time())
        logger.info(f"{caller} skipped (circuit open, {remaining}s remaining)")
        return ""

    try:
        body = json.dumps({
            "model": CHAT_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }).encode()
        t0 = time.time()
        req = urllib.request.Request(f"{LLM_API_BASE}/chat/completions", data=body, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        elapsed_ms = int((time.time() - t0) * 1000)
        usage = data.get("usage", {})
        # 成功则重置熔断
        _CONSECUTIVE_FAILURES = 0
        _CIRCUIT_OPEN_UNTIL = 0.0
        result = (msg.get("content", "") or "").strip()
        logger.info(
            f"{caller} OK model={CHAT_MODEL} tokens={usage.get('total_tokens', '?')} "
            f"({usage.get('prompt_tokens', '?')}p+{usage.get('completion_tokens', '?')}c) "
            f"time={elapsed_ms}ms result_len={len(result)}"
        )
        return result
    except Exception as e:
        _CONSECUTIVE_FAILURES += 1
        err_msg = str(e)
        is_402 = "402" in err_msg
        cooldown = _CIRCUIT_402_COOLDOWN_SECONDS if is_402 else CIRCUIT_COOLDOWN_SECONDS

        if _CONSECUTIVE_FAILURES >= CIRCUIT_BREAK_THRESHOLD:
            _CIRCUIT_OPEN_UNTIL = time.time() + cooldown
            logger.warning(
                f"circuit OPEN (cooldown {cooldown}s) after {_CONSECUTIVE_FAILURES} consecutive failures"
            )
        logger.warning(f"{caller} FAIL (fail #{_CONSECUTIVE_FAILURES}): {e}")
        return ""

def _parse_tags(raw_tags: list[str]) -> list[str]:
    from tag_library import TAG_LIBRARY_SORTED
    valid = [t for t in raw_tags if t in TAG_LIBRARY_SORTED]
    return valid[:10] if valid else raw_tags[:10]

def extract_tags(description: str) -> list[str]:
    if not description or len(description) < 20:
        return []
    from tag_library import build_prompt_section
    tag_list = build_prompt_section()
    text = description[:2000]
    result = _chat([
        {"role": "system", "content": f"你是一个游戏标签专家。根据游戏描述，从以下标签库中选择5-10个最匹配的中文标签，用逗号分隔。\n\n可用标签：{tag_list}\n\n规则：\n1. 只从标签库中选择，不要自创标签\n2. 选择与游戏最相关的标签\n3. 只返回标签，用逗号分隔，不要解释"},
        {"role": "user", "content": text},
    ], max_tokens=100, caller="extract_tags")
    if not result:
        return []
    raw_tags = [t.strip() for t in result.split(",") if t.strip()]
    valid = _parse_tags(raw_tags)
    logger.info(f"extract_tags result raw={raw_tags} valid={valid}")
    return valid

def enrich_game(description: str) -> list[str]:
    """提取游戏标签。仅在 sync_steam_data 新游戏时使用。"""
    if not description or len(description) < 20:
        return []
    from tag_library import build_prompt_section
    tag_list = build_prompt_section()
    text = description[:2000]
    result = _chat([
        {"role": "system", "content": (
            f"你是一个游戏标签专家。根据游戏描述，从以下标签库中选择5-10个最匹配的中文标签，用逗号分隔。\n\n"
            f"可用标签：{tag_list}\n\n"
            f"规则：\n1. 只从标签库中选择，不要自创标签\n2. 选择与游戏最相关的标签\n3. 只返回标签，用逗号分隔，不要解释"
        )},
        {"role": "user", "content": text},
    ], max_tokens=100, caller="enrich_game")
    if not result:
        return []
    raw_tags = [t.strip() for t in result.split(",") if t.strip()]
    valid = _parse_tags(raw_tags)
    logger.info(f"enrich_game tags={valid}")
    return valid

def translate_game_name(en_name: str) -> str:
    """翻译英文游戏名为中文。仅 daily_llm_enrich 中无中文名的游戏调用。"""
    if not en_name:
        return ""
    result = _chat([
        {"role": "system", "content": "你是游戏本地化专家。将英文游戏名翻译为简体中文名（不超过15字）。只返回中文名，不要解释或额外内容。"},
        {"role": "user", "content": en_name},
    ], max_tokens=20, caller="translate_game_name")
    if result:
        logger.info(f"translate_game_name en={en_name} -> cn={result}")
    return result[:30] if result else ""

def get_embedding(text: str) -> list[float]:
    return []

def embedding_available() -> bool:
    return False
