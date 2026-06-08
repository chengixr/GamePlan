"""图片处理管线：缩放、格式转换、URL 选择"""
import os
import logging
from PIL import Image

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADERS_DIR = os.path.join(BASE_DIR, "static", "images", "headers")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "static", "images", "screenshots")
STEAM_IMG_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"

os.makedirs(HEADERS_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

# 尺寸规格: (宽度,)
HEADER_SIZES = {"small": 400, "large": 920}
SCREENSHOT_SIZES = {"thumb": 216, "large": 1200}
FORMATS = {"webp": ("WEBP", 80), "jpg": ("JPEG", 82)}

CDN_FALLBACK_TEMPLATE = f"{STEAM_IMG_CDN}/{{appid}}/header.jpg"


def _resize_and_save(img: Image.Image, path_no_ext: str, max_width: int) -> dict:
    """按宽度等比缩放并保存 WebP + JPEG。返回 {fmt: url_path}"""
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        new_size = (max_width, int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    results = {}
    mode_rgb = img.mode
    for fmt, (pil_fmt, quality) in FORMATS.items():
        out_path = f"{path_no_ext}_{max_width}w.{fmt}"
        save_kwargs = {"quality": quality, "optimize": True}
        save_img = img
        if pil_fmt == "JPEG" and save_img.mode in ("RGBA", "P"):
            save_img = img.convert("RGB")
        save_img.save(out_path, pil_fmt, **save_kwargs)
        # 转换为 /static/... 相对路径
        rel = os.path.relpath(out_path, os.path.join(BASE_DIR, "static"))
        results[fmt] = f"/static/{rel}"
    return results


def process_header(appid: int, source_path: str) -> dict:
    """
    处理头图，生成 small(400w) + large(920w)，各输出 WebP + JPEG。
    返回: {"small": {"webp": "/static/...", "jpg": "..."}, "large": {...}}
    失败返回 {}。
    """
    if not os.path.exists(source_path):
        logger.warning(f"process_header: 源文件不存在 {source_path}")
        return {}
    try:
        base = os.path.join(HEADERS_DIR, str(appid))
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
    处理截图，生成 thumb(216w) + large(1200w)，各输出 WebP + JPEG。
    返回: {"thumb": {"webp": "..."}, "large": {...}}
    """
    if not os.path.exists(source_path):
        logger.warning(f"process_screenshot: 源文件不存在 {source_path}")
        return {}
    try:
        base = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}")
        result = {}
        for size_name, width in SCREENSHOT_SIZES.items():
            img = Image.open(source_path)
            result[size_name] = _resize_and_save(img, base, width)
            img.close()
        return result
    except Exception as e:
        logger.error(f"process_screenshot: appid={appid} idx={idx} 失败: {e}")
        return {}


def supports_webp(request_headers: dict) -> bool:
    """根据请求 Accept 头判断客户端是否支持 WebP"""
    accept = request_headers.get("accept", "")
    return "image/webp" in accept


def get_best_format(request_headers: dict) -> str:
    """返回最优图片格式扩展名: 'webp' 或 'jpg'"""
    return "webp" if supports_webp(request_headers) else "jpg"


def header_urls(appid: int, fmt: str) -> dict:
    """
    返回头图 URL 集合。本地文件不存在时回退 CDN。
    fmt: 'webp' 或 'jpg'
    返回: {"small": "/static/...", "large": "/static/...", "fallback": "https://..."}
    """
    fallback = CDN_FALLBACK_TEMPLATE.format(appid=appid)

    def _url(width):
        local = os.path.join(HEADERS_DIR, f"{appid}_{width}w.{fmt}")
        if os.path.exists(local):
            rel = os.path.relpath(local, os.path.join(BASE_DIR, "static"))
            return f"/static/{rel}"
        return ""

    small = _url(HEADER_SIZES["small"])
    large = _url(HEADER_SIZES["large"])
    return {"small": small or fallback, "large": large or fallback, "fallback": fallback}


def screenshot_urls(appid: int, count: int, fmt: str) -> list[dict]:
    """
    返回截图 URL 列表。
    fmt: 'webp' 或 'jpg'
    返回: [{"thumb": "/static/...", "large": "/static/..."}, ...]
    """
    results = []
    for idx in range(count):
        thumb_path = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}_{SCREENSHOT_SIZES['thumb']}w.{fmt}")
        large_path = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}_{SCREENSHOT_SIZES['large']}w.{fmt}")

        def _rel(p):
            if os.path.exists(p):
                return "/static/" + os.path.relpath(p, os.path.join(BASE_DIR, "static"))
            return ""

        thumb = _rel(thumb_path)
        large = _rel(large_path)
        if thumb or large:
            results.append({"thumb": thumb, "large": large})
    return results


def cdn_fallback(appid: int) -> str:
    """Steam CDN 回退 URL"""
    return CDN_FALLBACK_TEMPLATE.format(appid=appid)
