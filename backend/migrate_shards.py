"""将扁平目录中的图片迁移到分片目录结构，更新数据库 URL 路径"""
import os
import sys
import json
import logging
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import SessionLocal, Game
from image_processor import _shard, HEADERS_BASE, SCREENSHOTS_BASE

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("shard_migrate")


def _move_file(src: str, dst_dir: str) -> str | None:
    """移动文件到分片目录，返回新路径。已存在或移动失败返回 None"""
    if not os.path.exists(src):
        return None
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src))
    if os.path.exists(dst):
        # 目标已存在，删除源文件即可
        if not os.path.samefile(src, dst):
            os.remove(src)
        return dst
    try:
        shutil.move(src, dst)
        return dst
    except OSError as e:
        logger.warning(f"移动失败: {src} → {dst}: {e}")
        return None


def _migrate_files(base_dir: str, appid: int) -> dict:
    """移动某个 appid 的所有文件到分片目录。返回 {旧名: 新路径} 映射"""
    shard = _shard(appid)
    shard_dir = os.path.join(base_dir, shard)
    moved = {}

    flat_files = [
        f for f in os.listdir(base_dir)
        if f.startswith(f"{appid}_") and os.path.isfile(os.path.join(base_dir, f))
    ]
    for fname in flat_files:
        src = os.path.join(base_dir, fname)
        dst = _move_file(src, shard_dir)
        if dst:
            moved[fname] = dst

    return moved


def _update_url(url: str, appid: int, moved_map: dict) -> str:
    """更新单个 URL 路径，将扁平路径替换为分片路径"""
    if not url or not url.startswith("/static/"):
        return url
    shard = _shard(appid)
    # 扁平路径: /static/images/headers/{appid}_400w.webp
    # 分片路径: /static/images/headers/{shard}/{appid}_400w.webp
    for old_name, new_path in moved_map.items():
        if old_name in url:
            basename = os.path.basename(new_path)
            # 构建新的相对 URL
            rel = os.path.relpath(new_path, os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "static"))
            return "/static/" + rel
    # 如果路径中已有分片目录，跳过
    if f"/{shard}/" in url:
        return url
    return url


def main():
    parser = argparse.ArgumentParser(description="分片目录迁移")
    parser.add_argument("--dry-run", action="store_true", help="预览模式")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        games = db.query(Game).all()
        logger.info(f"共 {len(games)} 款游戏，开始分片迁移 {'(DRY-RUN)' if args.dry_run else ''}")

        h_moved = h_updated = 0
        s_moved = s_updated = 0

        for i, game in enumerate(games):
            appid = game.steam_app_id

            # 迁移头图文件
            h_map = _migrate_files(HEADERS_BASE, appid) if not args.dry_run else {}
            if h_map:
                h_moved += len(h_map)
                old_url = game.image_url
                old_large = game.image_large
                game.image_url = _update_url(old_url, appid, h_map)
                game.image_large = _update_url(old_large, appid, h_map)
                game.fallback_image = _update_url(game.fallback_image or "", appid, h_map)
                if game.image_url != old_url or game.image_large != old_large:
                    h_updated += 1

            # 迁移截图文件
            s_map = _migrate_files(SCREENSHOTS_BASE, appid) if not args.dry_run else {}
            if s_map:
                s_moved += len(s_map)
                try:
                    ss = json.loads(game.screenshots or "[]")
                    changed = False
                    for item in ss:
                        if isinstance(item, dict):
                            old_thumb = item.get("thumb", "")
                            new_thumb = _update_url(old_thumb, appid, s_map)
                            if new_thumb != old_thumb:
                                item["thumb"] = new_thumb
                                changed = True
                            old_large = item.get("large", "")
                            new_large = _update_url(old_large, appid, s_map)
                            if new_large != old_large:
                                item["large"] = new_large
                                changed = True
                    if changed:
                        game.screenshots = json.dumps(ss)
                        s_updated += 1
                except Exception:
                    pass

            if args.dry_run:
                # 统计待移动文件
                shard_h = _shard(appid)
                flat_headers = [f for f in os.listdir(HEADERS_BASE)
                               if f.startswith(f"{appid}_") and os.path.isfile(os.path.join(HEADERS_BASE, f))]
                flat_ss = [f for f in os.listdir(SCREENSHOTS_BASE)
                          if f.startswith(f"{appid}_") and os.path.isfile(os.path.join(SCREENSHOTS_BASE, f))]
                if flat_headers:
                    h_moved += len(flat_headers)
                    h_updated += 1
                if flat_ss:
                    s_moved += len(flat_ss)
                    s_updated += 1

                if flat_headers or flat_ss:
                    logger.info(f"[DRY-RUN] appid={appid}: 头图 {len(flat_headers)} + 截图 {len(flat_ss)} → shard/{shard_h}")

            if (i + 1) % 200 == 0:
                logger.info(f"进度: {i+1}/{len(games)}, 已移动 {h_moved + s_moved} 文件")
                if not args.dry_run:
                    db.commit()

        if not args.dry_run:
            db.commit()

        logger.info(f"分片迁移完成: 头图 {h_moved} 文件({h_updated} 游戏), 截图 {s_moved} 文件({s_updated} 游戏)")

        # 清理空目录
        if not args.dry_run:
            for d in [HEADERS_BASE, SCREENSHOTS_BASE]:
                try:
                    remaining = [f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]
                    if not remaining:
                        # 只记录，不删除目录本身（还有分片子目录在里面）
                        pass
                except Exception:
                    pass

    except Exception as e:
        db.rollback()
        logger.error(f"迁移失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
