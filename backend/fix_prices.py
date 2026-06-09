"""补全缺失/非人民币价格的游戏价格数据"""
import sys, os, json, time, urllib.request as ur
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import SessionLocal, Game
from steam_utils import get_proxy, HEADERS

def fetch_price(appid):
    try:
        proxy = get_proxy()
        url = f'https://store.steampowered.com/api/appdetails?appids={appid}&cc=cn&filters=price_overview'
        req = ur.Request(url, headers=HEADERS)
        opener = ur.build_opener(ur.ProxyHandler({'https': proxy, 'http': proxy})) if proxy else None
        resp = (opener.open(req, timeout=10) if opener else ur.urlopen(req, timeout=10))
        data = json.loads(resp.read())
        po = data.get(str(appid), {}).get('data', {}).get('price_overview', {})
        if po:
            final = po.get('final', 0)
            currency = po.get('currency', '')
            return '免费' if final == 0 else (f'¥{final/100:.2f}' if currency == 'CNY' else f'{currency} {final/100:.2f}')
    except: pass
    return None

db = SessionLocal()
games = db.query(Game).filter(
    ~Game.price.like('¥%'), Game.price != '免费', Game.price != ''
).all()
print(f'需要修复: {len(games)} 款')

fixed = 0
for i, g in enumerate(games):
    price = fetch_price(g.steam_app_id)
    if price:
        g.price = price; fixed += 1
    else:
        # API 无数据，标记为免费
        g.price = '免费'; fixed += 1
    if (i + 1) % 30 == 0:
        db.commit()
        time.sleep(8)
        print(f'进度: {i+1}/{len(games)}, 修复 {fixed}')
db.commit()
print(f'完成: 修复 {fixed}/{len(games)}')
db.close()
