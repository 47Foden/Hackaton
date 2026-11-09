"""Pretuning definitions derived from the shared ordering catalogue."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = json.loads((ROOT / 'order_catalog.json').read_text(encoding='utf-8'))
MENUS = [menu['name'] for menu in CATALOG]
if len(set(MENUS)) != len(MENUS):
    raise ValueError('Catalogue menu names must be unique')

BINARY_ATTRIBUTES = ['커피', '디카페인', '음료', '에스프레소', '라떼', '콜드브루',
                     '에이드', '프라페', '스무디', '주스', '논커피라떼', '티']
CATEGORIES = {attribute: [] for attribute in BINARY_ATTRIBUTES}
for menu in CATALOG:
    parent, child = menu['categories']
    if child == '스무디/주스':
        child = '주스' if '주스' in menu['name'] else '스무디'
    for attribute in (parent, child):
        CATEGORIES[attribute].append(menu['name'])

TASTE_ATTRIBUTES = ['단맛', '신맛', '쓴맛']
ATTRIBUTES = BINARY_ATTRIBUTES + TASTE_ATTRIBUTES
PRICES = json.loads((ROOT / 'menu_prices.json').read_text(encoding='utf-8'))
PRICE_OPTIONS = sorted(set(PRICES.values()))
