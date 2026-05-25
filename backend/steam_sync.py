import urllib.request
import urllib.request as ur
import json
import re
import time
import os
import logging
from datetime import date, datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from database import SessionLocal, game_tag_assoc, Game, Tag, DailyTopSeller
from tag_translations import translate_tag

logger = logging.getLogger(__name__)
STEAM_API = "https://store.steampowered.com/api"
STEAM_IMG_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"}

IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)


# ==================== 工具函数 ====================

def _get_proxy() -> str | None:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "config", "config.json")
    try:
        with open(config_path) as f:
            return json.load(f).get("proxy", {}).get("https") or None
    except Exception:
        return None

def _make_opener():
    proxy = _get_proxy()
    return ur.build_opener(ur.ProxyHandler({"https": proxy, "http": proxy})) if proxy else None

def _fetch_json(path: str, timeout: int = 20) -> dict:
    opener = _make_opener()
    req = ur.Request(f"{STEAM_API}/{path}", headers=HEADERS)
    resp = (opener.open(req, timeout=timeout) if opener else ur.urlopen(req, timeout=timeout))
    return json.loads(resp.read())

def _fetch_html(url: str, timeout: int = 15) -> str:
    opener = _make_opener()
    req = ur.Request(url, headers=HEADERS)
    resp = (opener.open(req, timeout=timeout) if opener else ur.urlopen(req, timeout=timeout))
    return resp.read().decode("utf-8", errors="ignore")

def _local_image_url(appid: int) -> str:
    return f"/static/images/{appid}.jpg"

def _local_image_path(appid: int) -> str:
    return os.path.join(IMAGES_DIR, f"{appid}.jpg")

def _download_image(appid: int) -> bool:
    local_path = _local_image_path(appid)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return True
    cdn_url = f"{STEAM_IMG_CDN}/{appid}/header.jpg"
    try:
        opener = _make_opener()
        req = ur.Request(cdn_url, headers=HEADERS)
        resp = (opener.open(req, timeout=12) if opener else ur.urlopen(req, timeout=12))
        with open(local_path, "wb") as f:
            f.write(resp.read())
        return True
    except Exception:
        return False


# ==================== 数据源 1: Steam featuredcategories API ====================

def sync_from_api() -> list[dict]:
    """从 featuredcategories API 获取游戏（名称、价格、图片）—— 最可靠"""
    items = []
    try:
        data = _fetch_json("featuredcategories", timeout=20)
        seen = set()
        for cat in ["top_sellers", "new_releases", "specials", "coming_soon"]:
            for item in data.get(cat, {}).get("items", []):
                appid = item.get("id")
                if appid and appid not in seen:
                    seen.add(appid)
                    final_price = item.get("final_price")
                    currency = item.get("currency", "USD")
                    if final_price is not None:
                        price = f"¥{final_price / 100:.2f}" if currency == "CNY" else f"{currency} {final_price / 100:.2f}"
                    else:
                        price = "免费"
                    img = item.get("header_image", "")
                    if not img:
                        img = f"{STEAM_IMG_CDN}/{appid}/header.jpg"
                    items.append({"appid": appid, "name": item.get("name", ""), "header_image": img, "price": price})
        logger.info(f"[API] featuredcategories: {len(items)} 款")
    except Exception as e:
        logger.warning(f"[API] featuredcategories 失败: {e}")
    return items


# ==================== 数据源 2: Steam 商店搜索页 HTML ====================

def _scrape_steam_search(filter_type: str, pages: int = 3) -> list[dict]:
    """爬 Steam 搜索页（topsellers / popularwishlist / toprated）"""
    items = []
    for page in range(pages):
        try:
            url = f"https://store.steampowered.com/search/?filter={filter_type}&page={page}"
            html = _fetch_html(url, timeout=15)
            appids = set()
            for m in re.finditer(r'data-ds-appid="(\d+)"', html):
                appids.add(int(m.group(1)))
            for appid in appids:
                items.append({
                    "appid": appid, "name": "",
                    "header_image": f"{STEAM_IMG_CDN}/{appid}/header.jpg", "price": "",
                })
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"[搜索] {filter_type} page={page} 失败: {e}")
            break
    logger.info(f"[搜索] {filter_type}: {len(items)} 款 ({pages} 页)")
    return items

def sync_from_search() -> list[dict]:
    """从 Steam 搜索页获取额外游戏（topsellers 10页）"""
    items = _scrape_steam_search("topsellers", pages=10)
    return items


# ==================== 数据源 3: SteamCharts.com ====================

def sync_from_steamcharts() -> list[dict]:
    """从 SteamCharts.com 获取热门游戏 + 玩家人数"""
    items = []
    try:
        html = _fetch_html("https://steamcharts.com/top", timeout=15)
        for m in re.finditer(r'<a href="/app/(\d+)[^"]*">([^<]+)</a>', html):
            appid = int(m.group(1))
            name = m.group(2).strip()
            items.append({
                "appid": appid, "name": name,
                "header_image": f"{STEAM_IMG_CDN}/{appid}/header.jpg", "price": "",
            })
        logger.info(f"[SteamCharts] top: {len(items)} 款")
    except Exception as e:
        logger.warning(f"[SteamCharts] 失败: {e}")
    return items


# ==================== 统一同步入口 ====================

def sync_steam_data():
    """多源同步：API → 搜索页 → SteamCharts，去重合并，分批获取详情"""
    db = SessionLocal()
    try:
        logger.info("=== 开始多源同步 ===")

        # 收集所有来源
        api_items = sync_from_api()
        search_items = sync_from_search()
        chart_items = sync_from_steamcharts()

        # 去重合并（API 数据优先，因为有名称和价格）
        merged = {}
        for item in api_items:
            merged[item["appid"]] = item
        for item in search_items:
            if item["appid"] not in merged:
                merged[item["appid"]] = item
        for item in chart_items:
            if item["appid"] not in merged:
                merged[item["appid"]] = item

        items = sorted(merged.values(), key=lambda x: list(merged.keys()).index(x["appid"]))
        logger.info(f"合并去重: {len(api_items)} + {len(search_items)} + {len(chart_items)} → {len(items)} 款")

        if not items:
            logger.warning("所有数据源均无返回，跳过同步")
            return

        today = date.today()
        existing_ids = {g[0] for g in db.query(Game.steam_app_id).all()}
        synced = updated = img_ok = detail_count = 0
        BATCH_SIZE = 30

        for rank, item in enumerate(items, 1):
            # 分批暂停，避免 Steam 限流
            if detail_count > 0 and detail_count % BATCH_SIZE == 0:
                logger.info(f"  已请求 {detail_count} 个详情，暂停 8 秒...")
                db.commit()
                time.sleep(8)
            appid = item["appid"]
            local_img = _local_image_url(appid)
            cdn_img = item.get("header_image") or f"{STEAM_IMG_CDN}/{appid}/header.jpg"

            if appid not in existing_ids:
                time.sleep(0.5)
                details = _try_fetch_details(appid); detail_count += 1

                downloaded = _download_image(appid)
                if downloaded:
                    img_ok += 1

                game = Game(
                    steam_app_id=appid,
                    name=item["name"],
                    name_cn=details.get("name_cn", "") if details else "",
                    description=details.get("description", "") if details else "",
                    image_url=local_img if downloaded else cdn_img,
                    price=item["price"],
                    release_date=details.get("release_date", "") if details else "",
                    screenshots=details.get("screenshots", "[]") if details else "[]",
                    review_summary=details.get("review_summary", "{}") if details else "{}",
                    reviews_synced_at=datetime.now(timezone.utc) if details else None,
                )
                db.add(game); db.flush()

                if details and details.get("tags"):
                    for tag_name in details["tags"]:
                        tag = db.query(Tag).filter(Tag.name == tag_name).first()
                        if not tag:
                            tag = Tag(name=tag_name)
                            db.add(tag); db.flush()
                        db.execute(game_tag_assoc.insert().values(game_id=game.id, tag_id=tag.id))

                gid = game.id
                existing_ids.add(appid)
                synced += 1
            else:
                game = db.query(Game).filter(Game.steam_app_id == appid).first()
                if game:
                    if os.path.exists(_local_image_path(appid)):
                        game.image_url = local_img
                    elif not game.image_url or game.image_url.startswith("/static"):
                        if _download_image(appid):
                            game.image_url = local_img
                            img_ok += 1
                        else:
                            game.image_url = cdn_img
                    # 判断是否需要补充 Steam 详细数据
                    need_details = (
                        game.reviews_synced_at is None or
                        (datetime.now(timezone.utc) - game.reviews_synced_at.replace(tzinfo=timezone.utc)) > timedelta(hours=24) or
                        not game.name_cn or
                        len(game.description or '') < 100 or
                        not game.tags
                    )
                    if need_details:
                        time.sleep(0.5)
                        d = _try_fetch_details(appid); detail_count += 1
                        if d:
                            # 截图和评价
                            game.screenshots = d.get("screenshots", "[]")
                            game.review_summary = d.get("review_summary", "{}")
                            game.reviews_synced_at = datetime.now(timezone.utc)
                            # 描述：用 Steam 详细描述替换简短描述
                            if d.get("description") and len(d["description"]) > len(game.description or ''):
                                game.description = d["description"]
                            # 中文名
                            if d.get("name_cn") and not game.name_cn:
                                game.name_cn = d["name_cn"]
                            # 标签
                            if d.get("tags"):
                                for tag_name in d["tags"]:
                                    tag = db.query(Tag).filter(Tag.name == tag_name).first()
                                    if not tag:
                                        tag = Tag(name=tag_name)
                                        db.add(tag); db.flush()
                                    db.execute(game_tag_assoc.insert().values(game_id=game.id, tag_id=tag.id))
                    game.updated_at = datetime.now(timezone.utc)
                gid = game.id if game else None
                updated += 1

            if gid:
                existing_today = db.query(DailyTopSeller).filter(
                    DailyTopSeller.game_id == gid, DailyTopSeller.date == today
                ).first()
                if not existing_today:
                    db.add(DailyTopSeller(game_id=gid, rank=rank, date=today))

        db.commit()
        logger.info(f"同步完成: 新增 {synced}, 更新 {updated}, 下载图片 {img_ok}, 共 {len(items)} 款")
    except Exception as e:
        db.rollback()
        logger.error(f"同步失败: {e}")
    finally:
        db.close()

def _try_fetch_details(appid: int) -> dict | None:
    try:
        data = _fetch_json(f"appdetails?appids={appid}&cc=cn&l=schinese", timeout=20)
        gd = data.get(str(appid), {}).get("data", {})
        if not gd.get("name"):
            return None
        tags = [translate_tag(g.get("description", "")) for g in gd.get("genres", [])]
        tags += [translate_tag(c.get("description", "")) for c in gd.get("categories", [])]

        screenshots = []
        for s in gd.get("screenshots", [])[:10]:
            url = s.get("path_full", "")
            if url:
                screenshots.append(url)

        recs = gd.get("recommendations", {})
        review_positive = recs.get("total", 0)
        total_reviews = recs.get("total_reviews", 0) or (review_positive * 100 // 80 if review_positive else 0)
        review_summary = json.dumps({"positive": review_positive, "total": total_reviews})

        return {
            "name_cn": gd.get("name", ""),
            "description": gd.get("detailed_description", "") or gd.get("short_description", ""),
            "release_date": gd.get("release_date", {}).get("date", ""),
            "tags": tags,
            "screenshots": json.dumps(screenshots),
            "review_summary": review_summary,
        }
    except Exception:
        return None


# ==================== 定时调度 ====================

_scheduler = None

def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(sync_steam_data, "cron", hour="0,6,12,18", minute=17)
    _scheduler.start()
    from threading import Timer
    Timer(30, sync_steam_data).start()

def shutdown_scheduler():
    if _scheduler:
        _scheduler.shutdown()
