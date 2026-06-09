"""用完整 appdetails API 重新验证所有免费游戏价格"""
import sys, os, json, time, urllib.request as ur
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import SessionLocal, Game
from steam_utils import get_proxy, HEADERS

def fetch_price(appid):
    try:
        proxy = get_proxy()
        url = f'https://store.steampowered.com/api/appdetails?appids={appid}&cc=cn'
        req = ur.Request(url, headers=HEADERS)
        opener = ur.build_opener(ur.ProxyHandler({'https': proxy, 'http': proxy})) if proxy else None
        resp = (opener.open(req, timeout=10) if opener else ur.urlopen(req, timeout=10))
        data = json.loads(resp.read())
        gd = data.get(str(appid), {}).get('data', {})
        if not gd: return None
        if gd.get('is_free', False): return '免费'
        po = gd.get('price_overview', {})
        if po:
            final = po.get('final', 0)
            currency = po.get('currency', '')
            if final == 0: return '免费'
            return f'¥{final/100:.2f}' if currency == 'CNY' else f'{currency} {final/100:.2f}'
    except: pass
    return None

db = SessionLocal()
games = db.query(Game).filter(Game.price == '免费').all()
print(f'验证 {len(games)} 款免费游戏价格...')

fixed = 0
for i, g in enumerate(games):
    price = fetch_price(g.steam_app_id)
    if price and price != '免费':
        g.price = price
        fixed += 1
        print(f'  修正: {g.name} (appid={g.steam_app_id}) -> {price}')
    if (i + 1) % 30 == 0:
        db.commit()
        time.sleep(8)
        print(f'进度: {i+1}/{len(games)}, 修正 {fixed}')
db.commit()
print(f'完成: {len(games)} 款中修正 {fixed} 款')
db.close()
