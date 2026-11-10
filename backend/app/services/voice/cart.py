"""Extract explicit named order lines; recommendations remain on their own path."""
import re
from app.schemas.voice import VoiceCart, VoiceCartItem
from app.services.voice.interpretation import _compact
from app.services.voice.options import TEMPERATURE_ALIASES as TEMPERATURES

def parse_cart(text, menus):
    phrase = _compact(text)
    # A request for suggestions must never silently become an order.
    if any(w in phrase for w in ("추천", "뭐가", "어떤")):
        return None
    names = sorted(((_compact(m["name"]), key) for key, m in menus.items()), key=lambda x: -len(x[0]))
    found = []
    pos = 0
    while pos < len(phrase):
        match = next(((name, key) for name, key in names if name and phrase.startswith(name, pos)), None)
        if match:
            name, key = match
            found.append((pos, pos + len(name), key))
            pos += len(name)
        else:
            pos += 1
    if not found or len(found) > 20:
        return None
    if len(found) == 1 and phrase == _compact(menus[found[0][2]]["name"]):
        return None
    lines = []
    counts = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5, "여섯": 6}
    for i, (start, end, key) in enumerate(found):
        menu = menus[key]
        if not menu["is_available"]:
            return None
        stop = found[i+1][0] if i+1 < len(found) else len(phrase)
        suffix = phrase[end:stop]
        prefix = phrase[:start] if i == 0 else phrase[found[i-1][1]:start]
        # Prefix temperature belongs to the menu immediately following it.
        temperatures = [(prefix.rfind(word), value) for word, value in TEMPERATURES.items() if prefix.endswith(word)]
        temperature = max(temperatures)[1] if temperatures else None
        if temperature and temperature not in menu["available_temperatures"]:
            return None
        quantity_match = re.search(r"(\d+|하나|한|둘|두|셋|세|넷|네|다섯|여섯)(?:잔|개)", suffix)
        quantity = counts.get(quantity_match[1], 0) or int(quantity_match[1]) if quantity_match else 1
        if not 1 <= quantity <= 99:
            return None
        variants = [v for v in menu.get("variants", []) if temperature is None or v["temperature"] == temperature]
        option_ids = []
        for variant in variants:
            for group in variant.get("option_groups", []):
                remaining = suffix
                for choice in sorted(group["choices"], key=lambda c: -len(_compact(c["label"]))):
                    label = _compact(choice["label"])
                    if label and label in remaining and choice["id"] not in option_ids:
                        option_ids.append(choice["id"])
                        remaining = remaining.replace(label, "", 1)
        lines.append(VoiceCartItem(menu_id=key, temperature=temperature, quantity=quantity, option_ids=option_ids))
    return VoiceCart(items=lines)
