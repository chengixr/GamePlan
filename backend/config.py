import os
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)

def _load_config():
    config_path = os.path.join(PROJECT_DIR, "config", "config.json")
    cfg = {}
    if os.path.isfile(config_path):
        with open(config_path) as f:
            cfg = json.load(f)
    return cfg

_cfg = _load_config()

BACKEND_PORT = int(os.environ.get("BACKEND_PORT", _cfg.get("backend", {}).get("port", 8000)))
BACKEND_HOST = os.environ.get("BACKEND_HOST", _cfg.get("backend", {}).get("host", "0.0.0.0"))
FRONTEND_PORT = int(os.environ.get("FRONTEND_PORT", _cfg.get("frontend", {}).get("port", 5173)))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    f"sqlite:///{os.path.join(BASE_DIR, _cfg.get('database', 'gameplan.db'))}"
)
SECRET_KEY = os.environ.get("SECRET_KEY", _cfg.get("secret_key", "dev-secret-change-in-production"))
SESSION_DAYS = int(os.environ.get("SESSION_DAYS", _cfg.get("session_days", 7)))

_llm = _cfg.get("llm", {})
LLM_ENABLED = os.environ.get("LLM_ENABLED", str(_llm.get("enabled", False))).lower() == "true"
LLM_API_BASE = os.environ.get("DEEPSEEK_API_BASE", _llm.get("api_base", "https://api.deepseek.com/v1"))
LLM_API_KEY = os.environ.get("DEEPSEEK_API_KEY", _llm.get("api_key", ""))
LLM_MODEL = os.environ.get("DEEPSEEK_MODEL", _llm.get("model", "deepseek-chat"))
LLM_EMBEDDING_MODEL = os.environ.get("DEEPSEEK_EMBEDDING", _llm.get("embedding_model", "deepseek-embed"))
