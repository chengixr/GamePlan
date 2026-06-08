# 图片存储与性能优化 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建图片处理管线，将 3.5GB 图片存储降至 ~350MB，前端按需加载合适尺寸。

**Architecture:** 新增 `image_processor.py` 作为图片处理核心模块（下载→缩放→WebP+JPEG双输出），修改同步逻辑限制截图数量并调用管线，API 层根据 Accept 头返回最优格式，前端 GameCard/GameDetail 使用对应尺寸。

**Tech Stack:** Python Pillow, Vue 3, FastAPI, SQLite

**依赖顺序:** image_processor.py → steam_sync.py → migrate_images.py → models.py + games.py → 前端组件

---

### Task 1: 新建图片处理管线 `image_processor.py`

**Files:**
- Create: `backend/image_processor.py`
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 新增 Pillow 依赖**

```bash
echo "Pillow==11.1.0" >> backend/requirements.txt
pip install Pillow==11.1.0
```

- [ ] **Step 2: 创建 image_processor.py**

写入 `backend/image_processor.py`：

```python
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

# 尺寸规格: (宽度, quality)
HEADER_SIZES = {"small": 400, "large": 920}
SCREENSHOT_SIZES = {"thumb": 216, "large": 1200}
FORMATS = {"webp": ("WEBP", 80), "jpg": ("JPEG", 82)}

CDN_FALLBACK_TEMPLATE = f"{STEAM_IMG_CDN}/{{appid}}/header.jpg"


def _resize_and_save(img: Image.Image, path_no_ext: str, max_width: int):
    """按宽度等比缩放并保存 WebP + JPEG。返回 {fmt: url_path}"""
    w, h = img.size
    if w > max_width:
        ratio = max_width / w
        new_size = (max_width, int(h * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    results = {}
    for fmt, (pil_fmt, quality) in FORMATS.items():
        out_path = f"{path_no_ext}_{max_width}w.{fmt}"
        save_kwargs = {"quality": quality, "optimize": True}
        if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        elif pil_fmt == "WEBP" and img.mode != "RGBA":
            img = img.convert("RGBA")
        img.save(out_path, pil_fmt, **save_kwargs)
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
        img = Image.open(source_path)
        base = os.path.join(HEADERS_DIR, str(appid))
        result = {}
        for size_name, width in HEADER_SIZES.items():
            # 每次 resize 需要原始图，所以重新打开
            img_copy = Image.open(source_path)
            result[size_name] = _resize_and_save(img_copy, base, width)
            img_copy.close()
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
        img = Image.open(source_path)
        base = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}")
        result = {}
        for size_name, width in SCREENSHOT_SIZES.items():
            img_copy = Image.open(source_path)
            result[size_name] = _resize_and_save(img_copy, base, width)
            img_copy.close()
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

    def _url(size_name, width):
        local = os.path.join(HEADERS_DIR, f"{appid}_{width}w.{fmt}")
        if os.path.exists(local):
            rel = os.path.relpath(local, os.path.join(BASE_DIR, "static"))
            return f"/static/{rel}"
        return ""

    small = _url("small", HEADER_SIZES["small"])
    large = _url("large", HEADER_SIZES["large"])
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
```

- [ ] **Step 3: 验证 Pillow 可正常导入**

```bash
cd backend && python -c "from image_processor import process_header, process_screenshot, supports_webp, header_urls; print('OK')"
```

- [ ] **Step 4: 提交**

```bash
git add backend/image_processor.py backend/requirements.txt
git commit -m "feat: 新增图片处理管线 image_processor

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: 修改 Steam 同步逻辑

**Files:**
- Modify: `backend/steam_sync.py`

将 `_download_image` 替换为下载→处理→返回多尺寸 URL 的流程，`_download_screenshots` 限制为 3 张并调用管线。

- [ ] **Step 1: 修改 _download_image 函数**

将 `backend/steam_sync.py:75-80` 的 `_download_image` 替换为 `_download_and_process_header`：

```python
def _download_and_process_header(appid: int, url: str = None) -> tuple[str, str, str]:
    """
    下载头图 → 管线处理 → 删除原图。
    返回 (small_url, large_url, fallback_url)，默认使用 webp 格式。
    """
    from image_processor import process_header, header_urls, cdn_fallback, HEADERS_DIR, HEADER_SIZES

    # 检查处理后的文件是否已存在
    existing = os.path.join(HEADERS_DIR, f"{appid}_{HEADER_SIZES['small']}w.webp")
    if os.path.exists(existing) and os.path.getsize(existing) > 0:
        urls = header_urls(appid, "webp")
        return urls["small"], urls["large"], urls["fallback"]

    # 下载原图
    tmp_path = os.path.join(IMAGES_DIR, f"{appid}_tmp.jpg")
    download_url = url or f"{STEAM_IMG_CDN}/{appid}/header.jpg"
    if not _curl_download(download_url, tmp_path):
        fallback = cdn_fallback(appid)
        return fallback, fallback, fallback

    # 管线处理
    result = process_header(appid, tmp_path)
    # 删除原图和临时文件
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
    old_path = _local_image_path(appid)
    if os.path.exists(old_path):
        os.remove(old_path)

    if not result:
        fallback = cdn_fallback(appid)
        return fallback, fallback, fallback

    urls = header_urls(appid, "webp")
    return urls["small"], urls["large"], urls["fallback"]
```

- [ ] **Step 2: 修改 _download_screenshots 函数**

将 `backend/steam_sync.py:83-95` 替换为 `_download_and_process_screenshots`：

```python
def _download_and_process_screenshots(appid: int, steam_urls: list[str]) -> list[dict]:
    """
    下载前 3 张截图 → 管线处理 → 删除原图。
    返回 [{"thumb": "/static/...", "large": "/static/..."}, ...]
    """
    from image_processor import process_screenshot, screenshot_urls

    # 检查是否已有处理后的文件
    existing = screenshot_urls(appid, 10, "webp")  # 尝试匹配已有
    if existing:
        return existing

    results = []
    for idx, url in enumerate(steam_urls[:3]):  # 最多 3 张
        tmp_path = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}_tmp.jpg")
        if not _curl_download(url, tmp_path, timeout=15):
            continue
        result = process_screenshot(appid, idx, tmp_path)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        # 删除旧格式原图
        old_path = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}.jpg")
        if os.path.exists(old_path):
            os.remove(old_path)
        if result:
            # 取 webp 格式作为默认存储引用
            results.append({
                "thumb": result.get("thumb", {}).get("webp", ""),
                "large": result.get("large", {}).get("webp", ""),
            })

    return results
```

- [ ] **Step 3: 修改 IMAGES_DIR 相关导入**

在 `backend/steam_sync.py` 文件顶部附近（`IMAGES_DIR` 定义后），添加 `from image_processor import` 的延迟导入说明（函数内部导入以避免循环依赖）。同时更新文件头部的常量引用，在 `_download_and_process_header` 中新增对 `HEADER_SIZES` 的引用。

- [ ] **Step 4: 修改 sync_steam_data 中的调用**

在 `sync_steam_data` 函数中，将第 273 行的 `_download_image` 调用替换为 `_download_and_process_header`，将第 287 行的 `screenshots` 赋值逻辑改为使用 `_download_and_process_screenshots` 的返回值。

修改 `sync_steam_data` 中新增游戏的部分（约第 269-303 行）：

```python
# 替换原来的 _download_image 调用（约第 273 行）
small_url, large_url, fallback = _download_and_process_header(appid, item.get("header_image"))

# 替换原来的 screenshots 赋值（约第 287 行）
screenshot_list = _download_and_process_screenshots(appid, details.get("steam_screenshot_urls", []) if details else [])

game = Game(
    steam_app_id=appid,
    name=en_name,
    name_cn=details.get("name_cn", "") if details else "",
    description=details.get("description", "") if details else "",
    image_url=small_url,
    image_large=large_url,
    fallback_image=fallback,
    price=item["price"],
    release_date=details.get("release_date", "") if details else "",
    screenshots=json.dumps(screenshot_list),
    review_summary=details.get("review_summary", "{}") if details else "{}",
    user_reviews=_fetch_user_reviews(appid) if details else "[]",
    reviews_synced_at=datetime.now(timezone.utc) if details else None,
)
```

- [ ] **Step 5: 修改 _try_fetch_details 返回原始截图 URL**

在 `_try_fetch_details` 中新增 `steam_screenshot_urls` 字段，保留原始 URL 供后续下载管线使用：

修改 `_try_fetch_details` 的 return 字典（约第 379-386 行），新增一行：

```python
return {
    "name": gd.get("name", ""),
    "name_cn": name_cn,
    "description": gd.get("detailed_description", "") or gd.get("short_description", ""),
    "release_date": gd.get("release_date", {}).get("date", ""),
    "tags": tags,
    "screenshots": json.dumps(screenshots),  # 保留兼容（管线处理后的本地 URL）
    "steam_screenshot_urls": steam_screenshot_urls,  # 新增：原始 Steam URL
    "review_summary": review_summary,
}
```

同时删除 `_try_fetch_details` 中原来的 `_download_screenshots` 调用（约第 372 行），改为只收集原始 URL：

```python
steam_screenshot_urls = []
for s in gd.get("screenshots", [])[:3]:  # 改为只收集前 3 张
    url = s.get("path_full", "")
    if url:
        steam_screenshot_urls.append(url)
```

- [ ] **Step 6: 修改已有游戏的更新逻辑**

在 `sync_steam_data` 的已有游戏更新分支（约第 305-328 行），同步适配新字段：

```python
else:
    game = db.query(Game).filter(Game.steam_app_id == appid).first()
    if game:
        from image_processor import header_urls, cdn_fallback
        # 检查本地处理后文件是否存在
        h_urls = header_urls(appid, "webp")
        if h_urls["small"]:
            game.image_url = h_urls["small"]
            game.image_large = h_urls["large"]
            game.fallback_image = h_urls["fallback"]
        elif not game.image_url.startswith("/static"):
            pass  # 保留已有 CDN 图片
        else:
            small_url, large_url, fallback = _download_and_process_header(appid, item.get("header_image"))
            game.image_url = small_url
            game.image_large = large_url
            game.fallback_image = fallback
        game.updated_at = datetime.now(timezone.utc)

        # 修复空截图
        if not game.screenshots or game.screenshots == "[]":
            try:
                d = _try_fetch_details(game.steam_app_id)
                if d and d.get("steam_screenshot_urls"):
                    ss = _download_and_process_screenshots(game.steam_app_id, d["steam_screenshot_urls"])
                    if ss:
                        game.screenshots = json.dumps(ss)
            except Exception:
                pass
```

- [ ] **Step 7: 在 steam_sync.py 顶部添加 json 导入**

确认 `import json` 已在文件顶部（当前第 2 行已有）。

- [ ] **Step 8: 提交**

```bash
git add backend/steam_sync.py
git commit -m "feat: 同步逻辑集成图片处理管线，限制截图 3 张

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: 新建历史数据迁移脚本

**Files:**
- Create: `backend/migrate_images.py`

- [ ] **Step 1: 创建 migrate_images.py**

写入 `backend/migrate_images.py`：

```python
"""历史图片迁移：将旧格式原图转为多尺寸 WebP + JPEG，更新数据库路径"""
import os
import sys
import json
import logging
import argparse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Game
from image_processor import (
    process_header, process_screenshot,
    header_urls, screenshot_urls,
    HEADERS_DIR, SCREENSHOTS_DIR
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate")

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images")
OLD_SCREENSHOTS_DIR = os.path.join(IMAGES_DIR, "screenshots")


def migrate_headers(db, dry_run=False):
    """迁移头图: static/images/{appid}.jpg → headers/{appid}_{size}w.{fmt}"""
    stats = {"ok": 0, "skip": 0, "fail": 0}
    games = db.query(Game).all()
    logger.info(f"共 {len(games)} 款游戏待检查头图")

    for game in games:
        appid = game.steam_app_id
        src = os.path.join(IMAGES_DIR, f"{appid}.jpg")

        # 检查是否已有处理后的文件
        h_urls = header_urls(appid, "webp")
        if h_urls["small"]:
            # 已处理，更新数据库路径
            if not dry_run:
                game.image_url = h_urls["small"]
                game.image_large = h_urls["large"]
                game.fallback_image = h_urls["fallback"]
            stats["skip"] += 1
            continue

        if not os.path.exists(src):
            stats["fail"] += 1
            continue

        if dry_run:
            logger.info(f"[DRY-RUN] 将处理头图: appid={appid}, src={src}")
            stats["ok"] += 1
            continue

        result = process_header(appid, src)
        if result:
            h_urls = header_urls(appid, "webp")
            game.image_url = h_urls["small"]
            game.image_large = h_urls["large"]
            game.fallback_image = h_urls["fallback"]
            stats["ok"] += 1
        else:
            stats["fail"] += 1

        if stats["ok"] % 50 == 0 and stats["ok"] > 0:
            logger.info(f"头图进度: {stats['ok']}/{len(games)}")
            if not dry_run:
                db.commit()

    if not dry_run:
        db.commit()
    logger.info(f"头图迁移完成: ok={stats['ok']}, skip={stats['skip']}, fail={stats['fail']}")
    return stats


def migrate_screenshots(db, dry_run=False):
    """迁移截图: screenshots/{appid}_{idx}.jpg → screenshots/{appid}_{idx}_{size}w.{fmt}"""
    stats = {"ok": 0, "skip": 0, "fail": 0, "files": 0}
    games = db.query(Game).filter(Game.screenshots != "[]", Game.screenshots.isnot(None)).all()
    logger.info(f"共 {len(games)} 款游戏待检查截图")

    for game in games:
        appid = game.steam_app_id
        try:
            old_ss = json.loads(game.screenshots or "[]")
        except Exception:
            continue

        # 检查新格式截图是否已存在
        new_ss = screenshot_urls(appid, 10, "webp")
        if new_ss:
            if not dry_run:
                game.screenshots = json.dumps(new_ss)
            stats["skip"] += 1
            continue

        # 遍历旧格式截图文件
        migrated = []
        for idx in range(10):  # 最多 10 张
            src = os.path.join(OLD_SCREENSHOTS_DIR, f"{appid}_{idx}.jpg")
            if not os.path.exists(src):
                continue
            stats["files"] += 1
            if dry_run:
                migrated.append({"thumb": f"/static/images/screenshots/{appid}_{idx}_216w.webp",
                                 "large": f"/static/images/screenshots/{appid}_{idx}_1200w.webp"})
                continue
            result = process_screenshot(appid, idx, src)
            if result:
                migrated.append({
                    "thumb": result.get("thumb", {}).get("webp", ""),
                    "large": result.get("large", {}).get("webp", ""),
                })
                stats["ok"] += 1
            else:
                stats["fail"] += 1

        if migrated and not dry_run:
            game.screenshots = json.dumps(migrated)

        if stats["files"] % 50 == 0 and stats["files"] > 0:
            logger.info(f"截图进度: {stats['files']} 文件, ok={stats['ok']}")
            if not dry_run:
                db.commit()

    if not dry_run:
        db.commit()
    logger.info(f"截图迁移完成: files={stats['files']}, ok={stats['ok']}, skip={stats['skip']}, fail={stats['fail']}")
    return stats


def main():
    parser = argparse.ArgumentParser(description="GamePlan 图片迁移脚本")
    parser.add_argument("--dry-run", action="store_true", help="预览模式，不实际修改")
    parser.add_argument("--headers-only", action="store_true", help="仅迁移头图")
    parser.add_argument("--screenshots-only", action="store_true", help="仅迁移截图")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        logger.info(f"开始迁移 {'(DRY-RUN)' if args.dry_run else ''}")

        if not args.screenshots_only:
            migrate_headers(db, args.dry_run)

        if not args.headers_only:
            migrate_screenshots(db, args.dry_run)

        logger.info("迁移完成")
    except Exception as e:
        db.rollback()
        logger.error(f"迁移失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 验证迁移脚本可解析参数**

```bash
cd backend && python migrate_images.py --help
```

预期输出：显示 --dry-run, --headers-only, --screenshots-only 参数说明。

- [ ] **Step 3: Dry-run 测试**

```bash
cd backend && python migrate_images.py --dry-run
```

预期：输出预览日志，不修改任何文件或数据库。

- [ ] **Step 4: 提交**

```bash
git add backend/migrate_images.py
git commit -m "feat: 新增历史图片迁移脚本

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: 更新数据库模型新增字段

**Files:**
- Modify: `backend/database.py`
- Modify: `backend/models.py`

- [ ] **Step 1: Game 表新增 fallback_image 和 image_large 字段**

在 `backend/database.py` 的 `Game` 类中 `image_url` 之后新增两列：

```python
# 在 image_url = Column(String(512), default="") 之后添加:
image_large = Column(String(512), default="")
fallback_image = Column(String(512), default="")
```

这两列在数据迁移和同步时写入。SQLite 会自动处理 `ALTER TABLE` 或由 SQLAlchemy `create_all` 自动添加。

- [ ] **Step 2: 更新 GameResponse 模型**

在 `backend/models.py` 的 `GameResponse` 类中新增字段：

```python
class GameResponse(BaseModel):
    id: int
    steam_app_id: int
    name: str
    name_cn: str = ""
    description: str
    image_url: str
    image_large: str = ""      # 新增
    fallback_image: str = ""   # 新增
    price: str
    tags: list[str] = []
```

- [ ] **Step 3: 验证数据库迁移**

```bash
cd backend && python -c "
from database import init_db, engine
from sqlalchemy import inspect
init_db()
inspector = inspect(engine)
cols = [c['name'] for c in inspector.get_columns('games')]
print('fallback_image' in cols)
print('image_large' in cols)
"
```

预期输出：
```
True
True
```

- [ ] **Step 4: 提交**

```bash
git add backend/database.py backend/models.py
git commit -m "feat: Game 表新增 image_large 和 fallback_image 字段

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: 更新 API 层返回多尺寸 URL

**Files:**
- Modify: `backend/games.py`

- [ ] **Step 1: 修改 top_sellers 端点**

将 `backend/games.py:67-91` 中构建 `GameResponse` 的部分改为使用新字段，并添加 `image_large`：

```python
all_items.append(GameResponse(
    id=game.id, steam_app_id=game.steam_app_id,
    name=game.name, name_cn=game.name_cn or "",
    description=game.description or "",
    image_url=game.image_url or "",
    image_large=game.image_large or game.image_url or "",
    fallback_image=game.fallback_image or "",
    price=game.price or "",
    tags=[t.name for t in game.tags],
))
```

同时移除旧的 fallback 计算逻辑（第 71-80 行的 `try/except` 块），因为 `fallback_image` 已在数据库中。

- [ ] **Step 2: 修改 recommended 端点**

将 `backend/games.py:110-131` 中构建 `GameResponse` 的部分同步修改：

```python
items.append(GameResponse(
    id=game.id,
    steam_app_id=game.steam_app_id,
    name=game.name,
    name_cn=game.name_cn or "",
    description=game.description or "",
    image_url=game.image_url or "",
    image_large=game.image_large or game.image_url or "",
    fallback_image=game.fallback_image or "",
    price=game.price or "",
    tags=[t.name for t in game.tags],
))
```

移除对应的 fallback 计算逻辑（第 111-119 行）。

- [ ] **Step 3: 修改 top_sellers/history 端点**

将 `backend/games.py:157-168` 中构建 `GameResponse` 的部分同步修改（新增两字段）。

- [ ] **Step 4: 修改 game_detail 端点**

在 `backend/games.py:237-250` 的返回字典中新增 `image_large` 和 `fallback_image` 字段：

```python
return {
    "id": game.id, "steam_app_id": game.steam_app_id,
    "name": game.name, "name_cn": game.name_cn or "",
    "description": game.description or "",
    "image_url": game.image_url or "",
    "image_large": game.image_large or game.image_url or "",
    "fallback_image": game.fallback_image or "",
    "price": game.price or "",
    "release_date": game.release_date or "",
    "tags": [t.name for t in game.tags],
    "screenshots": screenshots,  # 已是 [{"thumb": ..., "large": ...}] 格式
    "review_positive": review_positive,
    "review_total": review_total,
    "user_reviews": json.loads(game.user_reviews or "[]"),
    "similar_games": similar,
}
```

同时修改相似游戏列表中的 `GameResponse` 构造（约第 229-234 行），新增 `image_large` 和 `fallback_image`：

```python
similar.append(GameResponse(
    id=sg.id, steam_app_id=sg.steam_app_id, name=sg.name,
    name_cn=sg.name_cn or "", description=sg.description or "",
    image_url=sg.image_url or "",
    image_large=sg.image_large or sg.image_url or "",
    fallback_image=sg.fallback_image or "",
    price=sg.price or "",
    tags=[t.name for t in sg.tags],
))
```

- [ ] **Step 5: 验证 API 返回新字段**

启动后端后测试：

```bash
curl -s http://localhost:8000/api/games/1 | python -c "import sys,json; d=json.load(sys.stdin); print('image_large' in d, 'fallback_image' in d)"
```

预期输出：`True True`

- [ ] **Step 6: 提交**

```bash
git add backend/games.py
git commit -m "feat: API 层返回 image_large 和 fallback_image 字段

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: 前端 GameDetail 适配截图新结构

**Files:**
- Modify: `frontend/src/views/GameDetail.vue`

- [ ] **Step 1: 修改 screenshots 计算属性**

`GameDetail.vue` 中 `screenshots` 现在是 `[{"thumb": "...", "large": "..."}]` 格式。`currentImg` 需取 `.large`，缩略图需取 `.thumb`。

修改 `<script setup>` 中的 computed 属性（约第 136-137 行）：

```javascript
// 原:
const screenshots = computed(() => game.value?.screenshots || [])
const currentImg = computed(() => screenshots.value[activeIdx.value] || game.value?.image_url || '')

// 改为:
const screenshots = computed(() => {
  const raw = game.value?.screenshots || []
  // 兼容旧格式 (string[]) 和新格式 ([{thumb, large}])
  if (raw.length > 0 && typeof raw[0] === 'string') {
    return raw.map(s => ({ thumb: s, large: s }))
  }
  return raw
})
const currentImg = computed(() => {
  const ss = screenshots.value
  if (ss.length > 0 && ss[activeIdx.value]) {
    return ss[activeIdx.value].large || ss[activeIdx.value].thumb || ''
  }
  return game.value?.image_large || game.value?.image_url || ''
})
```

- [ ] **Step 2: 修改缩略图渲染模板**

将模板中第 41-44 行的缩略图部分 `:src="s"` 改为 `:src="s.thumb"`：

```html
<div class="thumbs">
  <img v-for="(s, i) in screenshots.slice(0, 8)" :key="i"
    :src="s.thumb || s.large || s"
    class="thumb" :class="{ active: i === activeIdx }"
    loading="lazy"
    @click="activeIdx = i" />
</div>
```

> `s.thumb || s.large || s` 兼容三种情况：新格式、旧 dict、旧 string。

- [ ] **Step 3: 修改 fallback hero 背景图**

第 7 行的 hero 背景图 `currentImg` 已在上方改为优先取 `image_large`。

- [ ] **Step 4: 提交**

```bash
git add frontend/src/views/GameDetail.vue
git commit -m "feat: GameDetail 适配截图新结构 {thumb, large}

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: 前端构建验证

**Files:**
- `frontend/src/components/GameCard.vue`（无需改动 — 自动使用 header_small）
- `frontend/src/views/HotView.vue`（无需改动 — 使用 GameCard）
- `frontend/src/views/RecommendView.vue`（无需改动 — 使用 GameCard）
- `frontend/src/views/FavoritesView.vue`（无需改动 — 使用 GameCard）

这三个视图均使用 `GameCard` 组件渲染。`GameCard` 的 `imgSrc` computed 使用 `image_url` 和 `fallback_image`，后端返回的 `image_url` 已是 header_small，`fallback_image` 是 Steam CDN URL，回退链正常工作，无需代码变更。

- [ ] **Step 1: 验证前端构建**

```bash
cd frontend && npm run build
```

预期：构建成功，无错误。

---

### Task 8: 端到端验证

- [ ] **Step 1: 测试 image_processor 单元功能**

```bash
cd backend && python -c "
from image_processor import supports_webp, get_best_format, header_urls, screenshot_urls, cdn_fallback

# 测试 WebP 检测
assert supports_webp({'accept': 'text/html,image/webp,*/*'}) == True
assert supports_webp({'accept': 'text/html'}) == False
assert get_best_format({'accept': 'image/webp'}) == 'webp'
assert get_best_format({'accept': '*/*'}) == 'jpg'

# 测试 CDN fallback
assert 'steamstatic.com' in cdn_fallback(730)

print('所有单元测试通过')
"
```

- [ ] **Step 2: 测试实际图片处理**

```bash
cd backend && python -c "
from PIL import Image
import os, tempfile

# 创建测试图片
tmp = tempfile.NamedTemporaryFile(suffix='.jpg', delete=False)
img = Image.new('RGB', (1920, 1080), color='red')
img.save(tmp.name, 'JPEG')
tmp.close()

from image_processor import process_header, process_screenshot
result = process_header(999999, tmp.name)
assert 'small' in result, f'small 缺失: {result}'
assert 'large' in result, f'large 缺失: {result}'
assert 'webp' in result['small'], f'webp 缺失'

# 验证生成的文件存在且小于原图
for size in ['small', 'large']:
    webp_path = os.path.join(os.path.dirname(__file__), 'static', 'images', 'headers', f'999999_{{\"small\":400,\"large\":920}[size]}w.webp')
    assert os.path.exists(webp_path), f'{webp_path} 不存在'
    size_kb = os.path.getsize(webp_path) / 1024
    print(f'{size} WebP: {size_kb:.1f} KB')
    assert size_kb < 50, f'{size} 太大: {size_kb} KB'

# 清理
import shutil
for f in os.listdir(os.path.join(os.path.dirname(__file__), 'static', 'images', 'headers')):
    if '999999' in f:
        os.remove(os.path.join(os.path.dirname(__file__), 'static', 'images', 'headers', f))
os.unlink(tmp.name)
print('图片处理测试通过')
"
```

- [ ] **Step 3: 生产构建验证**

```bash
cd frontend && npm run build
```

预期：构建成功。

- [ ] **Step 4: 启动后端验证无导入错误**

```bash
cd backend && timeout 5 python -c "
from image_processor import process_header, process_screenshot, header_urls, screenshot_urls
from steam_sync import _download_and_process_header, _download_and_process_screenshots
from models import GameResponse
from database import Game
print('所有导入成功')
" 2>&1
```

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "test: 端到端验证 - 图片处理管线、API 字段、前端构建

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### 执行顺序

```
Task 1 (image_processor.py) → Task 2 (steam_sync.py)
                            → Task 3 (migrate_images.py)
Task 4 (models + DB)        → Task 5 (games.py)
Task 5 (games.py)           → Task 6 (GameDetail) + Task 7 (构建验证)
Task 1-7 全部完成           → Task 8 (端到端验证)
```

实际执行可并行：Task 1+Task 4 可同时进行（无依赖），Task 3 依赖 Task 1，Task 2 依赖 Task 1+Task 4。
