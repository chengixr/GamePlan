"""Steam 公共工具函数 — steam_sync.py 和 ranking_sync.py 共享"""
import os
import json
import urllib.request as ur
import subprocess
import logging

logger = logging.getLogger(__name__)

STEAM_API = "https://store.steampowered.com/api"
STEAM_IMG_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
}


def get_proxy() -> str | None:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "config.json")
    try:
        with open(config_path) as f:
            return json.load(f).get("proxy", {}).get("https") or None
    except Exception:
        return None


def _make_opener():
    proxy = get_proxy()
    return ur.build_opener(ur.ProxyHandler({"https": proxy, "http": proxy})) if proxy else None


def fetch_json(path: str, timeout: int = 20) -> dict:
    opener = _make_opener()
    req = ur.Request(f"{STEAM_API}/{path}", headers=HEADERS)
    resp = (opener.open(req, timeout=timeout) if opener else ur.urlopen(req, timeout=timeout))
    return json.loads(resp.read())


def fetch_html(url: str, timeout: int = 15) -> str:
    opener = _make_opener()
    req = ur.Request(url, headers=HEADERS)
    resp = (opener.open(req, timeout=timeout) if opener else ur.urlopen(req, timeout=timeout))
    return resp.read().decode("utf-8", errors="ignore")


def curl_download(url: str, output_path: str, timeout: int = 12) -> bool:
    """使用 curl 下载文件，支持代理"""
    proxy = get_proxy()
    cmd = [
        "curl", "-s", "-L", "-o", output_path,
        "--max-time", str(timeout),
        "-H", f"User-Agent: {HEADERS['User-Agent']}",
    ]
    if proxy:
        cmd.extend(["--proxy", proxy])
    cmd.append(url)
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
        return result.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except (subprocess.SubprocessError, OSError):
        return False
