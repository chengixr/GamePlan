"""图片处理管线：缩放、格式转换、URL 选择。按 appid 分片存储避免单目录过大。"""
import os
import logging
from PIL import Image

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_ROOT = os.path.join(BASE_DIR, "static", "images")
HEADERS_BASE = os.path.join(IMAGES_ROOT, "headers")
SCREENSHOTS_BASE = os.path.join(IMAGES_ROOT, "screenshots")
STEAM_IMG_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"

# 尺寸规格
HEADER_SIZES = {"small": 400, "large": 920}
SCREENSHOT_SIZES = {"thumb": 216, "large": 1200}
FORMATS = {"webp": ("WEBP", 80)}

CDN_FALLBACK_TEMPLATE = f"{STEAM_IMG_CDN}/{{appid}}/header.jpg"


def _shard(appid: int) -> str:
    """返回分片子目录名，按 appid // 1000 分组"""
    return str(appid // 1000)


def _ensure_shard_dir(dirpath: str):
    os.makedirs(dirpath, exist_ok=True)


def _header_dir(appid: int) -> str:
    d = os.path.join(HEADERS_BASE, _shard(appid))
    _ensure_shard_dir(d)
    return d


def _screenshot_dir(appid: int) -> str:
    d = os.path.join(SCREENSHOTS_BASE, _shard(appid))
    _ensure_shard_dir(d)
    return d


def _resize_and_save(img: Image.Image, path_no_ext: str, max_width: int) -> dict:
    """按宽度等比缩放并保存 WebP。返回 {fmt: url_path}"""
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        new_size = (max_width, int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    results = {}
    for fmt, (pil_fmt, quality) in FORMATS.items():
        out_path = f"{path_no_ext}_{max_width}w.{fmt}"
        save_kwargs = {"quality": quality, "optimize": True}
        img.save(out_path, pil_fmt, **save_kwargs)
        rel = os.path.relpath(out_path, os.path.join(BASE_DIR, "static"))
        results[fmt] = f"/static/{rel}"
    return results


def process_header(appid: int, source_path: str) -> dict:
    """
    处理头图，生成 small(400w) + large(920w)，输出 WebP。
    返回: {"small": {"webp": "/static/..."}, "large": {...}}
    失败返回 {}。
    """
    if not os.path.exists(source_path):
        logger.warning(f"process_header: 源文件不存在 {source_path}")
        return {}
    try:
        d = _header_dir(appid)
        base = os.path.join(d, str(appid))
        result = {}
        for size_name, width in HEADER_SIZES.items():
            img = Image.open(source_path)
            result[size_name] = _resize_and_save(img, base, width)
            img.close()
        logger.info(f"process_header: appid={appid} OK")
        return result
    except Exception as e:
        logger.error(f"process_header: appid={appid} 失败: {e}")
        return {}


def process_screenshot(appid: int, idx: int, source_path: str) -> dict:
    """
    处理截图，生成 thumb(216w) + large(1200w)，输出 WebP。
    返回: {"thumb": {"webp": "..."}, "large": {...}}
    """
    if not os.path.exists(source_path):
        logger.warning(f"process_screenshot: 源文件不存在 {source_path}")
        return {}
    try:
        d = _screenshot_dir(appid)
        base = os.path.join(d, f"{appid}_{idx}")
        result = {}
        for size_name, width in SCREENSHOT_SIZES.items():
            img = Image.open(source_path)
            result[size_name] = _resize_and_save(img, base, width)
            img.close()
        return result
    except Exception as e:
        logger.error(f"process_screenshot: appid={appid} idx={idx} 失败: {e}")
        return {}


def get_best_format(request_headers: dict = None) -> str:
    """返回图片格式扩展名，统一使用 webp"""
    return "webp"


def header_urls(appid: int, fmt: str) -> dict:
    """
    返回头图 URL 集合。本地文件不存在时回退 CDN。
    返回: {"small": "/static/...", "large": "/static/...", "fallback": "https://..."}
    """
    fallback = CDN_FALLBACK_TEMPLATE.format(appid=appid)
    d = _header_dir(appid)

    def _url(width):
        local = os.path.join(d, f"{appid}_{width}w.{fmt}")
        if os.path.exists(local):
            rel = os.path.relpath(local, os.path.join(BASE_DIR, "static"))
            return f"/static/{rel}"
        # 兼容旧路径（扁平目录，迁移前数据）
        old_local = os.path.join(HEADERS_BASE, f"{appid}_{width}w.{fmt}")
        if os.path.exists(old_local):
            rel = os.path.relpath(old_local, os.path.join(BASE_DIR, "static"))
            return f"/static/{rel}"
        return ""

    small = _url(HEADER_SIZES["small"])
    large = _url(HEADER_SIZES["large"])
    return {"small": small or fallback, "large": large or fallback, "fallback": fallback}


def screenshot_urls(appid: int, count: int, fmt: str) -> list[dict]:
    """
    返回截图 URL 列表。支持新旧两种路径结构。
    返回: [{"thumb": "/static/...", "large": "/static/..."}, ...]
    """
    results = []
    d = _screenshot_dir(appid)

    for idx in range(count):
        thumb_new = os.path.join(d, f"{appid}_{idx}_{SCREENSHOT_SIZES['thumb']}w.{fmt}")
        large_new = os.path.join(d, f"{appid}_{idx}_{SCREENSHOT_SIZES['large']}w.{fmt}")
        thumb_old = os.path.join(SCREENSHOTS_BASE, f"{appid}_{idx}_{SCREENSHOT_SIZES['thumb']}w.{fmt}")
        large_old = os.path.join(SCREENSHOTS_BASE, f"{appid}_{idx}_{SCREENSHOT_SIZES['large']}w.{fmt}")

        def _rel(*paths):
            for p in paths:
                if os.path.exists(p):
                    return "/static/" + os.path.relpath(p, os.path.join(BASE_DIR, "static"))
            return ""

        thumb = _rel(thumb_new, thumb_old)
        large = _rel(large_new, large_old)
        if thumb or large:
            results.append({"thumb": thumb, "large": large})
    return results


def cdn_fallback(appid: int) -> str:
    """Steam CDN 回退 URL"""
    return CDN_FALLBACK_TEMPLATE.format(appid=appid)
