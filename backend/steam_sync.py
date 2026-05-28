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

SCREENSHOTS_DIR = os.path.join(IMAGES_DIR, "screenshots")
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


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


def _download_screenshots(appid: int, steam_urls: list[str]) -> list[str]:
    """下载截图到本地，返回本地 URL 列表。未下载成功的保留原始 URL。"""
    local_urls = []
    for idx, url in enumerate(steam_urls):
        local_path = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}.jpg")
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            local_urls.append(f"/static/images/screenshots/{appid}_{idx}.jpg")
            continue
        try:
            opener = _make_opener()
            req = ur.Request(url, headers=HEADERS)
            resp = (opener.open(req, timeout=15) if opener else ur.urlopen(req, timeout=15))
            with open(local_path, "wb") as f:
                f.write(resp.read())
            local_urls.append(f"/static/images/screenshots/{appid}_{idx}.jpg")
        except Exception:
            local_urls.append(url)  # 下载失败保留原始 URL
    return local_urls


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
                    user_reviews=_fetch_user_reviews(appid) if details else "[]",
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
                            game.screenshots = d.get("screenshots", "[]")
                            game.review_summary = d.get("review_summary", "{}")
                            game.reviews_synced_at = datetime.now(timezone.utc)
                            # 用户评价
                            if not game.user_reviews or game.user_reviews == "[]":
                                game.user_reviews = _fetch_user_reviews(appid)
                            # 描述：用 Steam 详细描述替换简短描述
                            if d.get("description") and len(d["description"]) > len(game.description or ''):
                                game.description = d["description"]
                            # 中文名
                            if d.get("name_cn") and not game.name_cn:
                                game.name_cn = d["name_cn"]
                            # 标签
                            if d.get("tags"):
                                # 清除旧标签关联
                                db.execute(game_tag_assoc.delete().where(game_tag_assoc.c.game_id == game.id))
                                seen_tags = set()
                                for tag_name in d["tags"]:
                                    if tag_name in seen_tags:
                                        continue
                                    seen_tags.add(tag_name)
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
        from games import clear_hot_cache
        clear_hot_cache()
        from recommender import clear_recommender_cache
        clear_recommender_cache()
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

        # LLM 标签补充
        desc_for_llm = gd.get("detailed_description", "") or gd.get("short_description", "")
        if desc_for_llm:
            try:
                from llm import extract_tags
                llm_tags = extract_tags(desc_for_llm)
                for t in llm_tags:
                    if t not in tags:
                        tags.append(t)
            except: pass

        # 去重：合并相近标签，去除低价值标签
        from tag_library import dedup_tags
        tags = dedup_tags(tags)

        screenshots = []
        steam_screenshot_urls = []
        for s in gd.get("screenshots", [])[:10]:
            url = s.get("path_full", "")
            if url:
                steam_screenshot_urls.append(url)

        # 下载截图到本地
        screenshots = _download_screenshots(appid, steam_screenshot_urls)

        recs = gd.get("recommendations", {})
        review_positive = recs.get("total", 0)
        total_reviews = recs.get("total_reviews", 0) or (review_positive * 100 // 80 if review_positive else 0)
        review_summary = json.dumps({"positive": review_positive, "total": total_reviews})

        name_cn = gd.get("name", "")
        # LLM 生成中文名（如果 Steam 没返回中文名或与英文名相同则用 LLM）
        if not name_cn or name_cn == gd.get("name", "") or not any('\u4e00' <= c <= '\u9fff' for c in name_cn):
            try:
                from llm import generate_chinese_name
                llm_cn = generate_chinese_name(
                    gd.get("name", ""),
                    gd.get("short_description", "") or gd.get("detailed_description", "")
                )
                if llm_cn:
                    name_cn = llm_cn
            except: pass

        return {
            "name_cn": name_cn,
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

def _fetch_user_reviews(appid: int) -> str:
    """获取 Steam 用户评价（12条中文）"""
    try:
        url = f"https://store.steampowered.com/appreviews/{appid}?json=1&num_per_page=12&language=schinese&review_type=all"
        opener = _make_opener()
        req = ur.Request(url, headers=HEADERS)
        resp = (opener.open(req, timeout=15) if opener else ur.urlopen(req, timeout=15))
        data = json.loads(resp.read())
        reviews = []
        for r in data.get("reviews", []):
            reviews.append({
                "text": r.get("review", "")[:500],
                "voted_up": r.get("voted_up", True),
                "playtime": r.get("author", {}).get("playtime_forever", 0),
            })
        return json.dumps(reviews)
    except Exception as e:
        logger.warning(f"获取评价 {appid} 失败: {e}")
        return "[]"

def catchup_sync():
    """
    19:00 追补同步：整合当天未录入的游戏 + 库中已有游戏的缺漏数据
    1. 尝试从 Steam 数据源再抓一次热销榜
    2. 对当天未收录的游戏，补录排名并拉取详情
    3. 对库中已有但数据不全的游戏，补充截图/描述/标签
    """
    today = date.today()
    logger.info("=== 开始追补同步 (19:00) ===")
    db = SessionLocal()
    try:
        # 1. 收集当天已有排名的游戏 ID
        today_entries = db.query(DailyTopSeller).filter(DailyTopSeller.date == today).all()
        today_game_ids = {e.game_id for e in today_entries}

        # 2. 收集所有数据源的游戏（最后一次尝试）
        from_games = sync_from_api()
        from_search = sync_from_search()
        from_charts = sync_from_steamcharts()
        all_ids = set()
        merge = {}
        for item in from_games + from_search + from_charts:
            aid = item["appid"]
            if aid not in all_ids:
                all_ids.add(aid)
                merge[aid] = item
        logger.info(f"追补合并: {len(from_games)} + {len(from_search)} + {len(from_charts)} → {len(merge)} 款")

        # 3. 补录当天缺失的排名
        catchup_rank = 0
        for rank, item in enumerate(merge.values(), 1):
            game = db.query(Game).filter(Game.steam_app_id == item["appid"]).first()
            gid = game.id if game else None
            if gid and gid not in today_game_ids:
                db.add(DailyTopSeller(game_id=gid, rank=rank, date=today))
                catchup_rank += 1

        # 4. 补充数据缺失的游戏（截图/描述为空）
        incomplete = db.query(Game).filter(
            (Game.screenshots == "[]") | (Game.screenshots.is_(None)) |
            (Game.description == "") | (Game.description.is_(None)) |
            (Game.reviews_synced_at.is_(None))
        ).limit(50).all()

        detail_ok = 0
        img_ok = 0
        for game in incomplete:
            try:
                d = _try_fetch_details(game.steam_app_id)
                if d:
                    if not game.screenshots or game.screenshots == "[]":
                        game.screenshots = d.get("screenshots", "[]")
                        img_ok += 1
                    if not game.description:
                        game.description = d.get("description", "")
                    if not game.name_cn:
                        game.name_cn = d.get("name_cn", "")
                    if not game.tags and d.get("tags"):
                        for tag_name in d["tags"]:
                            tag = db.query(Tag).filter(Tag.name == tag_name).first()
                            if not tag:
                                tag = Tag(name=tag_name)
                                db.add(tag); db.flush()
                            db.execute(game_tag_assoc.insert().values(game_id=game.id, tag_id=tag.id))
                    game.reviews_synced_at = datetime.now(timezone.utc)
                    detail_ok += 1
            except Exception as e:
                logger.warning(f"追补详情 {game.steam_app_id} 失败: {e}")

        db.commit()
        from games import clear_hot_cache
        clear_hot_cache()
        from recommender import clear_recommender_cache
        clear_recommender_cache()
        logger.info(f"追补完成: 补排名 {catchup_rank}, 补详情 {detail_ok}, 补截图 {img_ok}")
    except Exception as e:
        db.rollback()
        logger.error(f"追补同步失败: {e}")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(sync_steam_data, "cron", hour="0,6,12,18", minute=17)
    # 每天 19:17 追补同步
    _scheduler.add_job(catchup_sync, "cron", hour=19, minute=17)
    # 每天凌晨 3 点清理过期日志
    from logger_config import clean_old_logs
    _scheduler.add_job(clean_old_logs, "cron", hour=3, minute=0)
    _scheduler.start()
    from threading import Timer
    Timer(30, sync_steam_data).start()

def shutdown_scheduler():
    if _scheduler:
        _scheduler.shutdown()
