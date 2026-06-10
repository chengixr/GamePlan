"""修复数据库中错误的 Steam App ID 和价格。
问题根因：种子数据中多个游戏的 App ID 错误，导致系统展示的游戏名称和价格属于其他游戏。
修复策略：
1. 将错误 App ID 更新为正确值
2. 从 Steam API 重新拉取名称和价格
3. 处理重复冲突：如果正确 App ID 已存在，删除错误记录
"""
import sys, os, json, time, urllib.request as ur
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import SessionLocal, Game, DailyTopSeller, game_tag_assoc

# 已知的错误 App ID → 正确 App ID 映射
# 格式: old_appid → (correct_appid, correct_name_zh)
APPID_FIXES = {
    # 730940 是 LOST SPHEAR Demo(免费) → 正确 RDR2 = 1174180
    730940: (1174180, "Red Dead Redemption 2", "荒野大镖客：救赎2"),
    # 1203220 是 NARAKA: BLADEPOINT(免费) → 正确 Stardew Valley = 413150
    1203220: (413150, "Stardew Valley", "星露谷物语"),
    # 2677660 是 Indiana Jones → 正确 Marvel Rivals = 2767030
    2677660: (2767030, "Marvel Rivals", "漫威争锋"),
    # 1377580 是 Soulworker(免费) → 正确 Sons Of The Forest = 1326470
    1377580: (1326470, "Sons Of The Forest", "森林之子"),
    # 1030840 是 Mafia: Definitive Edition → 正确 HELLDIVERS 2 = 553850
    1030840: (553850, "HELLDIVERS 2", "绝地潜兵2"),
    # 2239550 是 Watch Dogs: Legion → 正确 Monster Hunter Wilds = 2246340
    2239550: (2246340, "Monster Hunter Wilds", "怪物猎人：荒野"),
    # 1229490 是 ULTRAKILL → 正确 Brotato = 1942280
    1229490: (1942280, "Brotato", "土豆兄弟"),
    # 1238810 是 Battlefield V → 正确 Battlefield 2042 = 1517290
    1238810: (1517290, "Battlefield 2042", "战地2042"),
    # 1740720 是 Have a Nice Death → 正确 Ready or Not = 1144200
    1740720: (1144200, "Ready or Not", "严阵以待"),
    # 1248130 是 Farming Simulator 22 → 正确 FS25 = 2300320
    1248130: (2300320, "Farming Simulator 25", "模拟农场 25"),
    # 1250410 是 MSFS 2020 → 正确 MSFS 2024 = 2537590
    1250410: (2537590, "Microsoft Flight Simulator 2024", "微软飞行模拟 2024"),
}

# 同时修复名称不正确的记录（保持正确 App ID，但名称不对）
NAME_FIXES = {
    # 1174180 数据库叫 "Red Dead Redemption"，实际 Steam 叫 "Red Dead Redemption 2"
    1174180: ("Red Dead Redemption 2", "荒野大镖客：救赎2"),
}

db = SessionLocal()
try:
    print("=== 开始修复数据库错误 App ID 和价格 ===\n")

    # Step 1: 修复错误 App ID
    for old_appid, (new_appid, correct_name, correct_name_cn) in APPID_FIXES.items():
        game = db.query(Game).filter(Game.steam_app_id == old_appid).first()
        if not game:
            print(f"[SKIP] App ID {old_appid} - 数据库中不存在")
            continue

        # 检查正确 App ID 是否已在数据库中
        existing = db.query(Game).filter(Game.steam_app_id == new_appid).first()
        if existing:
            print(f"[DELETE] ID={game.id} appid={old_appid} ({game.name}) - 正确 App ID {new_appid} 已存在 ID={existing.id} ({existing.name})")
            # 删除 DailyTopSeller 关联
            db.query(DailyTopSeller).filter(DailyTopSeller.game_id == game.id).delete()
            # 删除标签关联
            db.execute(game_tag_assoc.delete().where(game_tag_assoc.c.game_id == game.id))
            db.delete(game)
        else:
            print(f"[FIX] ID={game.id} appid {old_appid} → {new_appid}")
            print(f"     名称: {game.name} → {correct_name}")
            print(f"     中文名: {game.name_cn} → {correct_name_cn}")
            game.steam_app_id = new_appid
            game.name = correct_name
            game.name_cn = correct_name_cn

    # Step 2: 修复名称不正确的记录
    for appid, (correct_name, correct_name_cn) in NAME_FIXES.items():
        game = db.query(Game).filter(Game.steam_app_id == appid).first()
        if game and game.name != correct_name:
            print(f"[NAME] ID={game.id} appid={appid}: {game.name} → {correct_name}")
            game.name = correct_name
            if correct_name_cn:
                game.name_cn = correct_name_cn

    db.commit()
    print("\n=== App ID 修复完成 ===\n")

    # Step 3: 验证修复后的游戏通过 Steam API 获取正确价格
    print("=== 验证游戏价格 ===")
    # 获取修复涉及的所有 App ID
    verify_appids = set()
    for old_appid, (new_appid, _, _) in APPID_FIXES.items():
        verify_appids.add(new_appid)
    for appid in NAME_FIXES:
        verify_appids.add(appid)

    # 也验证所有显示"免费"的种子游戏
    free_games = db.query(Game).filter(Game.price == "免费", Game.id <= 80).all()
    for g in free_games:
        verify_appids.add(g.steam_app_id)

    # 通过 Steam API 验证价格
    from steam_utils import get_proxy, HEADERS
    proxy = get_proxy()

    price_updated = 0
    for i, appid in enumerate(sorted(verify_appids)):
        game = db.query(Game).filter(Game.steam_app_id == appid).first()
        if not game:
            continue
        try:
            url = f'https://store.steampowered.com/api/appdetails?appids={appid}&cc=cn'
            req = ur.Request(url, headers=HEADERS)
            opener = ur.build_opener(ur.ProxyHandler({'https': proxy, 'http': proxy})) if proxy else None
            resp = (opener.open(req, timeout=10) if opener else ur.urlopen(req, timeout=10))
            data = json.loads(resp.read())
            gd = data.get(str(appid), {}).get('data', {})
            if not gd.get('name'):
                print(f'  [{appid}] API 无数据，跳过')
                continue

            is_free = gd.get('is_free', False)
            po = gd.get('price_overview', {})
            final = po.get('final', 0)
            currency = po.get('currency', '')

            if is_free or not po:
                expected_price = '免费'
            elif final == 0:
                expected_price = ''  # 数据异常，保持原样
            elif currency == 'CNY':
                expected_price = f'¥{final/100:.2f}' if final % 100 != 0 else f'¥{int(final/100)}'
            else:
                expected_price = f'{currency} {final/100:.2f}'

            current_price = game.price
            if expected_price and expected_price != current_price:
                print(f'  [{appid}] {game.name}: {current_price} → {expected_price}')
                game.price = expected_price
                price_updated += 1
            else:
                print(f'  [{appid}] {game.name}: {current_price} ✓')

            time.sleep(0.5)
        except Exception as e:
            print(f'  [{appid}] {game.name}: API 错误 - {str(e)[:80]}')

        if (i + 1) % 10 == 0:
            db.commit()
            print(f'  已处理 {i+1}/{len(verify_appids)}，更新 {price_updated} 个价格')
            time.sleep(5)

    db.commit()
    print(f'\n价格验证完成: 共验证 {len(verify_appids)} 款，更新 {price_updated} 个价格')

    # Step 4: 清理已删除游戏引用的图片（可选）
    from games import clear_hot_cache
    clear_hot_cache()
    from recommender import clear_recommender_cache
    clear_recommender_cache()

    print("\n=== 全部修复完成 ===")

except Exception as e:
    db.rollback()
    print(f"修复失败: {e}")
    raise
finally:
    db.close()
