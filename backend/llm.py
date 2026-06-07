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

def generate_chinese_name(en_name: str, description: str) -> str:
    if not en_name:
        return ""
    result = _chat([
        {"role": "system", "content": "你是一个游戏本地化专家。根据英文游戏名和描述，生成一个简洁的中文名（不超过15字）。只返回中文名，不要解释。"},
        {"role": "user", "content": f"游戏名: {en_name}\n描述: {description[:1000]}"},
    ], max_tokens=30, caller="generate_chinese_name")
    if result:
        logger.info(f"generate_chinese_name en={en_name} -> cn={result}")
    return result[:30] if result else ""

def enrich_game(en_name: str, description: str) -> tuple[list[str], str]:
    """合并标签提取和中文名生成为一次 API 调用。仅在 sync_steam_data 新游戏时使用。"""
    if not en_name or not description or len(description) < 20:
        return [], ""
    from tag_library import build_prompt_section
    tag_list = build_prompt_section()
    text = description[:2000]
    result = _chat([
        {"role": "system", "content": (
            f"你是游戏信息提取专家。根据游戏名和描述，完成两项任务。\n\n"
            f"任务1 - 标签：从以下标签库选择5-10个最匹配的中文标签。\n可用标签：{tag_list}\n"
            f"规则：只从库中选择，不要自创。\n\n"
            f"任务2 - 中文名：生成简洁中文名（不超过15字），如果英文名已有中文含义可直接采用。\n\n"
            f"返回格式（严格遵守）：\n标签: 标签1, 标签2, 标签3\n中文名: 游戏中文名"
        )},
        {"role": "user", "content": f"游戏名: {en_name}\n描述: {text}"},
    ], max_tokens=150, caller="enrich_game")
    if not result:
        return [], ""

    tags: list[str] = []
    name_cn = ""
    for line in result.split("\n"):
        line = line.strip()
        if line.startswith("标签:") or line.startswith("标签："):
            tag_part = line.split(":", 1)[-1].split("：", 1)[-1].strip()
            tags = [t.strip() for t in tag_part.split(",") if t.strip()]
        elif line.startswith("中文名:") or line.startswith("中文名："):
            name_cn = line.split(":", 1)[-1].split("：", 1)[-1].strip()[:30]

    tags = _parse_tags(tags)
    logger.info(f"enrich_game en={en_name} tags={tags} cn={name_cn}")
    return tags, name_cn

def get_embedding(text: str) -> list[float]:
    return []

def embedding_available() -> bool:
    return False
