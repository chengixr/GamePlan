"""轻量级 Steam 排名同步 — 每小时抓取排名数据，库中缺失的游戏自动触发详情同步。"""

import re
import os
import json
import time
import urllib.request as ur
import logging
from datetime import datetime, timezone
from database import SessionLocal, Game, SteamRanking, Tag, game_tag_assoc
from steam_utils import (
    get_proxy, fetch_json, fetch_html, curl_download, STEAM_IMG_CDN, HEADERS
)

logger = logging.getLogger(__name__)
IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images")
SCREENSHOTS_DIR = os.path.join(IMAGES_DIR, "screenshots")


def _local_image_url(appid: int) -> str:
    return f"/static/images/{appid}.jpg"


def _local_image_path(appid: int) -> str:
    return os.path.join(IMAGES_DIR, f"{appid}.jpg")


def _download_image(appid: int, url: str = None) -> bool:
    local_path = _local_image_path(appid)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return True
    download_url = url or f"{STEAM_IMG_CDN}/{appid}/header.jpg"
    return curl_download(download_url, local_path)


def _download_screenshots(appid: int, steam_urls: list[str]) -> list[str]:
    local_urls = []
    for idx, url in enumerate(steam_urls):
        local_path = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}.jpg")
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            local_urls.append(f"/static/images/screenshots/{appid}_{idx}.jpg")
            continue
        if curl_download(url, local_path, timeout=15):
            local_urls.append(f"/static/images/screenshots/{appid}_{idx}.jpg")
        else:
            local_urls.append(url)
    return local_urls


def _fetch_game_details(appid: int) -> dict | None:
    """获取单个游戏的详情数据，用于创建库记录。"""
    try:
        data = fetch_json(f"appdetails?appids={appid}&cc=cn&l=schinese", timeout=20)
        gd = data.get(str(appid), {}).get("data", {})
        if not gd.get("name"):
            return None

        from tag_translations import translate_tag
        tags = [translate_tag(g.get("description", "")) for g in gd.get("genres", [])]

        from tag_library import dedup_tags
        tags = dedup_tags(tags)

        recs = gd.get("recommendations", {})
        review_positive = recs.get("total", 0)
        total_reviews = recs.get("total_reviews", 0) or (review_positive * 100 // 80 if review_positive else 0)

        name_cn = gd.get("name", "")

        # 提取价格
        price = ""
        if gd.get("is_free", False):
            price = "免费"
        else:
            po = gd.get("price_overview", {})
            if po:
                final = po.get("final", 0)
                currency = po.get("currency", "")
                if final > 0:
                    price = f"¥{final / 100:.2f}" if currency == "CNY" else f"{currency} {final / 100:.2f}"

        return {
            "name": gd.get("name", ""),
            "name_cn": name_cn,
            "description": gd.get("detailed_description", "") or gd.get("short_description", ""),
            "header_image": gd.get("header_image", ""),
            "price": price,
            "release_date": gd.get("release_date", {}).get("date", ""),
            "tags": tags,
            "review_summary": json.dumps({"positive": review_positive, "total": total_reviews}),
            "screenshot_urls": [s.get("path_full", "") for s in gd.get("screenshots", [])[:10] if s.get("path_full")],
        }
    except Exception:
        return None


def sync_rankings():
    """从 Steam 搜索页抓取热销排名快照（前 100 名）。库中缺失的游戏自动拉取详情入库。"""
    db = SessionLocal()
    try:
        appids = []
        titles = []
        seen = set()
        html = fetch_html(
            "https://store.steampowered.com/search/?filter=topsellers&cc=cn&page=0&count=100",
            timeout=15,
        )
        page_titles = re.findall(r'class="title">([^<]+)', html)
        for m in re.finditer(r'data-ds-appid="(\d+)"', html):
            aid = int(m.group(1))
            if aid not in seen:
                seen.add(aid)
                appids.append(aid)
                idx = len(appids) - 1
                titles.append(page_titles[idx] if idx < len(page_titles) else "")

        if not appids:
            logger.warning("[排名同步] 搜索页无数据，跳过")
            return

        # 查找库中已有的 appid
        existing = {g[0] for g in db.query(Game.steam_app_id).all()}
        missing = [aid for aid in appids if aid not in existing]

        logger.info(f"[排名同步] 排名 {len(appids)} 款，库中缺失 {len(missing)} 款")

        # 写入排名快照
        now = datetime.now(timezone.utc)
        for rank, (aid, name) in enumerate(zip(appids, titles), 1):
            db.add(SteamRanking(
                steam_app_id=aid, name=name.strip(),
                rank=rank, snapshot_time=now,
            ))
        db.commit()

        # 同步缺失游戏
        if missing:
            synced = 0
            for aid in missing:
                details = _fetch_game_details(aid)
                if not details:
                    continue
                time.sleep(0.3)  # 避免 Steam 限流

                # 下载头图 + 截图，失败则使用 CDN URL
                downloaded = _download_image(aid, details.get("header_image"))
                image_url = _local_image_url(aid) if downloaded else (details.get("header_image") or f"{STEAM_IMG_CDN}/{aid}/header.jpg")

                screenshot_urls = details.get("screenshot_urls", [])
                screenshots = json.dumps(_download_screenshots(aid, screenshot_urls)) if screenshot_urls else "[]"

                game = Game(
                    steam_app_id=aid,
                    name=details["name"],
                    name_cn=details.get("name_cn", ""),
                    description=details.get("description", ""),
                    image_url=image_url,
                    screenshots=screenshots,
                    price=details.get("price", ""),
                    release_date=details.get("release_date", ""),
                    review_summary=details.get("review_summary", "{}"),
                    reviews_synced_at=now,
                )
                db.add(game)
                db.flush()

                for tag_name in details.get("tags", []):
                    tag = db.query(Tag).filter(Tag.name == tag_name).first()
                    if not tag:
                        tag = Tag(name=tag_name)
                        db.add(tag)
                        db.flush()
                    db.execute(game_tag_assoc.insert().values(game_id=game.id, tag_id=tag.id))

                synced += 1
                if synced % 5 == 0:
                    db.commit()

            db.commit()
            if synced:
                from recommender import clear_recommender_cache
                clear_recommender_cache()
            logger.info(f"[排名同步] 详情入库 {synced}/{len(missing)} 款新游戏")

        from games import clear_hot_cache
        clear_hot_cache()
        logger.info(f"[排名同步] 写入 {len(appids)} 条排名快照")
    except Exception as e:
        db.rollback()
        logger.warning(f"[排名同步] 失败: {e}")
    finally:
        db.close()
