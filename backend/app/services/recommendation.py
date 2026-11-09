"""Rule-based Korean preference extraction and deterministic Pretuning ranking."""
import csv
import math
import os
import re
from pathlib import Path
ALIASES = {'레몬 아이스티': '레몬티', '말차라떼': '녹차라떼'}
# These names identify the frozen score snapshot. Catalog names may change.
SCORE_MENU_IDS = {
    "복숭아 아이스티": "peach_iced_tea", "레몬티": "lemon_tea_alias",
    "아이스아메리카노": "iced_americano", "레몬에이드": "lemonade",
    "딸기라떼": "strawberry_latte", "청포도에이드": "green_grape_ade",
    "카페라떼": "cafe_latte", "레몬차": "lemon_tea", "유자차": "citron_tea",
    "에스프레소": "espresso", "녹차라떼": "green_tea_latte",
}
TASTES = {'단맛': r'단맛|달달|달콤|달지|달게|달은|단(?=거|음료|커피|차|티|라떼)',
          '신맛': r'신맛|새콤|상큼|시지|신(?=거|음료|커피|차|티)',
          '쓴맛': r'쓴맛|쌉싸름|쓰지|쓴(?=거|음료|커피|차|티)'}
NEG = r'안|덜|적|않|없|낮|빼|말고'


def parse_preferences(text):
    text = re.sub(r'\s+', '', text)
    if '카페인' in text or '디카페인' in text:
        raise ValueError('카페인 데이터는 아직 준비되지 않았어요. 맛이나 음료 종류로 말씀해 주세요.')
    tastes = {}
    matches = sorted((m.start(), m.end(), name) for name, pattern in TASTES.items() for m in re.finditer(pattern, text))
    for i, (start, end, name) in enumerate(matches):
        left = matches[i-1][1] if i else 0
        right = matches[i+1][0] if i+1 < len(matches) else len(text)
        # Postfixed negatives attach to this taste; prefixed negatives attach after a conjunction.
        prefix = re.split(r'고|지만|면서|며|은|는', text[left:start])[-1]
        suffix = re.split(r'고|지만|면서|며|,', text[end:right])[0]
        negative = bool(re.search(NEG, prefix + suffix))
        tastes[name] = -1 if negative else 1
    category = next((c for c in ['논커피라떼', '에이드', '라떼', '커피', '티'] if c in text), None)
    if category is None and re.search(r'차(?:종류|추천|아무거나|주세요|$)', text): category = '티'
    if category and re.search(re.escape(category) + r'(?:는|가|은)?(?:말고|아닌|빼)', text):
        raise ValueError('음료 종류 제외 조건은 아직 지원하지 않아요. 원하는 종류를 말씀해 주세요.')
    temperature = 'COLD' if any(w in text for w in ['차갑', '시원', '아이스']) else 'HOT' if any(w in text for w in ['뜨겁', '따뜻']) else None
    price = re.search(r'(\d[\d,]*)원?(이하|미만|이상|초과)', text)
    price_filter = (int(price[1].replace(',', '')), price[2]) if price else None
    if not tastes and not category and not temperature and not price_filter and not any(w in text for w in ['추천', '아무거나']):
        raise ValueError('원하는 맛이나 음료 종류를 다시 말씀해 주세요.')
    return tastes, category, temperature, price_filter


def load_scores():
    root = Path(os.environ.get('COMMON_DIR', Path(__file__).resolve().parents[3] / 'common')) / 'recommendation'
    tables = []
    for file, columns, binary in [('continuous.csv', list(TASTES), False), ('binary.csv', ['커피','티','에이드','라떼','논커피라떼'], True)]:
        table = {}
        with (root / file).open(encoding='utf-8-sig', newline='') as stream:
            for row in csv.DictReader(stream):
                name = ALIASES.get(row['메뉴'], row['메뉴'])
                menu_id = SCORE_MENU_IDS.get(name)
                if menu_id is None or menu_id in table: raise ValueError('Invalid menu mapping')
                values = {c: float(row[c]) for c in columns}
                if any(not math.isfinite(v) or not 0 <= v <= 1 or (binary and v not in (0,1)) for v in values.values()):
                    raise ValueError('Invalid score')
                table[menu_id] = values
        if set(table) != set(SCORE_MENU_IDS.values()): raise ValueError('Incomplete dataset')
        tables.append(table)
    return tables


def recommend(text, menus):
    tastes, category, temperature, price = parse_preferences(text)
    continuous, binary = load_scores()
    ranked = []
    for menu in menus:
        menu_id = menu['menu_id']
        if not menu['is_available'] or menu_id not in continuous: continue
        if category and not binary[menu_id][category]: continue
        if temperature and temperature not in menu['available_temperatures']: continue
        if price:
            amount, op = price; value = menu['price_krw']
            if not {'이하': value <= amount, '미만': value < amount, '이상': value >= amount, '초과': value > amount}[op]: continue
        # A negative attribute reverses only that attribute, never unrelated tastes.
        weights = tastes or {t: 1 for t in TASTES}
        score = sum(continuous[menu_id][t] if direction > 0 else 1-continuous[menu_id][t] for t,direction in weights.items()) / len(weights)
        ranked.append((score, menu_id))
    return [mid for _,mid in sorted(ranked, key=lambda item: (-item[0], item[1]))[:4]]
