"""历史图片迁移：将旧格式原图转为多尺寸 WebP + JPEG，更新数据库路径"""
import os
import sys
import json
import logging
import argparse

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

        # 检查是否已有处理后的文件（本地路径非 CDN）
        h_urls = header_urls(appid, "webp")
        if h_urls["small"] and h_urls["small"].startswith("/static/"):
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
