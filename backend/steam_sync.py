import urllib.request as ur
import json
import re
import time
import os
import logging
import subprocess
from datetime import date, datetime, timezone
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

def _curl_download(url: str, output_path: str, timeout: int = 12) -> bool:
    """使用 curl 下载文件，支持代理"""
    proxy = _get_proxy()
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


def _download_image(appid: int, url: str = None) -> bool:
    local_path = _local_image_path(appid)
    if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
        return True
    download_url = url or f"{STEAM_IMG_CDN}/{appid}/header.jpg"
    return _curl_download(download_url, local_path)


def _download_screenshots(appid: int, steam_urls: list[str]) -> list[str]:
    """下载截图到本地，返回本地 URL 列表。未下载成功的保留原始 URL。"""
    local_urls = []
    for idx, url in enumerate(steam_urls):
        local_path = os.path.join(SCREENSHOTS_DIR, f"{appid}_{idx}.jpg")
        if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
            local_urls.append(f"/static/images/screenshots/{appid}_{idx}.jpg")
            continue
        if _curl_download(url, local_path, timeout=15):
            local_urls.append(f"/static/images/screenshots/{appid}_{idx}.jpg")
        else:
            local_urls.append(url)
    return local_urls


# ==================== 数据源 1: Steam featuredcategories API ====================

def sync_from_api() -> tuple[list[dict], list[dict]]:
    """从 featuredcategories API 获取游戏，返回 (热销榜, 其他发现)。
    热销榜用于元数据富化，其他类别用于扩展游戏库。"""
    top_sellers = []
    discovery = []
    try:
        data = _fetch_json("featuredcategories", timeout=20)
        seen = set()

        def _parse_item(item):
            appid = item.get("id")
            if not appid or appid in seen:
                return None
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
            return {"appid": appid, "name": item.get("name", ""), "header_image": img, "price": price}

        for item in data.get("top_sellers", {}).get("items", []):
            parsed = _parse_item(item)
            if parsed:
                top_sellers.append(parsed)

        for cat in ["new_releases", "specials", "coming_soon"]:
            for item in data.get(cat, {}).get("items", []):
                parsed = _parse_item(item)
                if parsed:
                    discovery.append(parsed)

        logger.info(f"[API] 热销 {len(top_sellers)} + 发现 {len(discovery)} 款")
    except Exception as e:
        logger.warning(f"[API] featuredcategories 失败: {e}")
    return top_sellers, discovery


# ==================== 数据源 2: Steam 商店搜索页 HTML ====================

def _scrape_steam_search(filter_type: str, pages: int = 3) -> list[dict]:
    """爬 Steam 搜索页（topsellers / popularwishlist / toprated）"""
    items = []
    seen = set()
    for page in range(pages):
        try:
            url = f"https://store.steampowered.com/search/?filter={filter_type}&cc=cn&page={page}"
            html = _fetch_html(url, timeout=15)
            new_count = 0
            for m in re.finditer(r'data-ds-appid="(\d+)"', html):
                appid = int(m.group(1))
                if appid not in seen:
                    seen.add(appid)
                    new_count += 1
                    items.append({
                        "appid": appid, "name": "",
                        "header_image": f"{STEAM_IMG_CDN}/{appid}/header.jpg", "price": "",
                    })
            if new_count == 0:
                logger.info(f"[搜索] {filter_type} page={page} 无新增，终止翻页")
                break
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
    """多源同步：搜索页排序 → API 元数据富化 → SteamCharts 补充，分批获取详情"""
    db = SessionLocal()
    try:
        logger.info("=== 开始多源同步 ===")

        # 收集数据
        api_top, api_discovery = sync_from_api()   # API: 热销元数据 + 发现类游戏
        search_items = sync_from_search()           # 搜索页: 主排名源（filter=topsellers）
        chart_items = sync_from_steamcharts()        # SteamCharts: 补充

        # 构建 API 元数据查找表（热销 + 发现）
        api_lookup = {}
        for item in api_top + api_discovery:
            if item["appid"] not in api_lookup:
                api_lookup[item["appid"]] = item

        # 以搜索页排序为基准，API 数据富化名称和价格
        merged = {}
        ranked_order = []

        for item in search_items:
            aid = item["appid"]
            if aid in api_lookup:
                merged[aid] = api_lookup[aid]  # 用 API 数据（有名称和价格）
            else:
                merged[aid] = item
            ranked_order.append(aid)

        # 追加 API 热销榜中搜索页遗漏的游戏
        for item in api_top:
            if item["appid"] not in merged:
                merged[item["appid"]] = item
                ranked_order.append(item["appid"])

        # 追加 API 发现类游戏（new_releases/specials/coming_soon）
        for item in api_discovery:
            if item["appid"] not in merged:
                merged[item["appid"]] = item
                ranked_order.append(item["appid"])

        # 追加 SteamCharts
        for item in chart_items:
            if item["appid"] not in merged:
                merged[item["appid"]] = item
                ranked_order.append(item["appid"])

        items = [merged[aid] for aid in ranked_order]
        logger.info(f"合并: 搜索 {len(search_items)} + API热销 {len(api_top)} + 发现 {len(api_discovery)} + Charts {len(chart_items)} → {len(items)} 款")

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

                downloaded = _download_image(appid, item.get("header_image"))
                if downloaded:
                    img_ok += 1

                # 名称优先用 details，避免搜索抓取的空名
                en_name = (details.get("name", "") if details else "") or item.get("name", "")
                game = Game(
                    steam_app_id=appid,
                    name=en_name,
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
                    elif game.image_url and not game.image_url.startswith("/static"):
                        pass  # 保留已有 CDN 图片
                    else:
                        # 尝试重新下载头图
                        if _download_image(appid, item.get("header_image")):
                            game.image_url = local_img
                        else:
                            game.image_url = cdn_img
                    game.updated_at = datetime.now(timezone.utc)

                    # 修复空截图：仅在截图缺失时拉取详情
                    if not game.screenshots or game.screenshots == "[]":
                        try:
                            d = _try_fetch_details(game.steam_app_id)
                            if d and d.get("screenshots") and d["screenshots"] != "[]":
                                game.screenshots = d["screenshots"]
                        except Exception:
                            pass
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

        name_cn = gd.get("name", "")

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

        return {
            "name": gd.get("name", ""),
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
_job_status: dict[str, dict] = {}

def get_job_status() -> dict:
    return dict(_job_status)

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
        from_api_top, from_api_disc = sync_from_api()
        from_search = sync_from_search()
        from_charts = sync_from_steamcharts()
        all_ids = set()
        merge = {}
        for item in from_search + from_api_top + from_api_disc + from_charts:
            aid = item["appid"]
            if aid not in all_ids:
                all_ids.add(aid)
                merge[aid] = item
        logger.info(f"追补合并: 搜索 {len(from_search)} + API {len(from_api_top)+len(from_api_disc)} + Charts {len(from_charts)} → {len(merge)} 款")

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


def daily_llm_enrich():
    """每天 23:00 对当日热销榜中未处理的游戏统一调用 LLM 提取标签。"""
    from datetime import date
    from llm import enrich_game, _is_available, _circuit_is_open

    if not _is_available():
        logger.info("[llm] daily_llm_enrich 跳过 (LLM disabled)")
        return
    if _circuit_is_open():
        logger.info("[llm] daily_llm_enrich 跳过 (circuit open)")
        return

    today = date.today()
    db = SessionLocal()
    try:
        # 当日热销榜中未 LLM 处理的游戏
        today_ids = {row[0] for row in db.query(DailyTopSeller.game_id).filter(DailyTopSeller.date == today).all()}
        if not today_ids:
            logger.info(f"[llm] daily_llm_enrich: {today} 无热销榜数据，跳过")
            return

        games = db.query(Game).filter(
            Game.id.in_(today_ids),
            Game.llm_tags_enriched == False,
            Game.description != "",
        ).all()

        if not games:
            logger.info(f"[llm] daily_llm_enrich: {today} 热销榜 {len(today_ids)} 款游戏均已处理，跳过")
            return

        logger.info(f"[llm] daily_llm_enrich: {today} 热销榜 {len(today_ids)} 款，未处理 {len(games)} 款，开始提取标签")

        enriched = 0
        for game in games:
            desc = (game.description or "")[:2000]
            if len(desc) < 20:
                game.llm_tags_enriched = True
                continue
            try:
                llm_tags = enrich_game(desc)
                if llm_tags:
                    for tag_name in llm_tags:
                        tag = db.query(Tag).filter(Tag.name == tag_name).first()
                        if not tag:
                            tag = Tag(name=tag_name)
                            db.add(tag); db.flush()
                        existing_assoc = db.execute(
                            game_tag_assoc.select().where(
                                game_tag_assoc.c.game_id == game.id,
                                game_tag_assoc.c.tag_id == tag.id,
                            )
                        ).first()
                        if not existing_assoc:
                            db.execute(game_tag_assoc.insert().values(game_id=game.id, tag_id=tag.id))
                    enriched += 1
                game.llm_tags_enriched = True
            except Exception as e:
                logger.warning(f"[llm] daily_llm_enrich 游戏 {game.steam_app_id} 失败: {e}")
                # 熔断检查：如果 circuit open 则终止后续处理
                if _circuit_is_open():
                    logger.warning("[llm] daily_llm_enrich 熔断，终止后续处理")
                    break

            if enriched % 10 == 0 and enriched > 0:
                db.commit()
                logger.info(f"[llm] daily_llm_enrich 进度: {enriched}/{len(games)}")

        db.commit()
        from recommender import clear_recommender_cache
        clear_recommender_cache()
        logger.info(f"[llm] daily_llm_enrich 完成: {enriched}/{len(games)} 款游戏已提取标签")
    except Exception as e:
        db.rollback()
        logger.error(f"[llm] daily_llm_enrich 异常: {e}")
    finally:
        db.close()


def start_scheduler():
    global _scheduler
    from datetime import datetime, timezone
    from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

    _scheduler = BackgroundScheduler()

    def _on_job_executed(event):
        _job_status[event.job_id] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "last_status": "success",
            "last_error": None,
        }

    def _on_job_error(event):
        _job_status[event.job_id] = {
            "last_run": datetime.now(timezone.utc).isoformat(),
            "last_status": "failed",
            "last_error": str(event.exception)[:500] if event.exception else "未知错误",
        }

    _scheduler.add_listener(_on_job_executed, EVENT_JOB_EXECUTED)
    _scheduler.add_listener(_on_job_error, EVENT_JOB_ERROR)

    # 每小时同步 Steam 排名快照（仅排名和名称）
    from ranking_sync import sync_rankings
    _scheduler.add_job(sync_rankings, "cron", minute=13, id="sync_rankings")
    # 每 6 小时同步完整游戏详情
    _scheduler.add_job(sync_steam_data, "cron", hour="0,6,12,18", minute=17, id="sync_steam_data")
    # 每天 19:17 追补同步
    _scheduler.add_job(catchup_sync, "cron", hour=19, minute=17, id="catchup_sync")
    # 每天 23:00 统一 LLM 标签提取
    _scheduler.add_job(daily_llm_enrich, "cron", hour=23, minute=7, id="daily_llm_enrich")
    # 每天凌晨 3 点清理过期日志
    from logger_config import clean_old_logs
    _scheduler.add_job(clean_old_logs, "cron", hour=3, minute=0, id="clean_old_logs")

    for job in _scheduler.get_jobs():
        if job.id not in _job_status:
            _job_status[job.id] = {"last_run": None, "last_status": "pending", "last_error": None}

    _scheduler.start()
    from threading import Timer
    Timer(10, sync_rankings).start()
    Timer(30, sync_steam_data).start()

def shutdown_scheduler():
    if _scheduler:
        _scheduler.shutdown()
