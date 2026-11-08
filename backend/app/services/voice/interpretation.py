from unicodedata import normalize

from app.schemas.voice import Confirm, Recommend, Retry, SelectMenu, SetServiceType, SetTemperature, VoiceAction, VoiceStage

POLITE_ENDINGS = ("으로해주세요", "로해주세요", "하나주세요", "한잔주세요", "해주실래요", "해주세요", "주세요", "부탁해요")
TEMPERATURES = {
    "뜨겁게": "HOT", "따뜻하게": "HOT", "뜨거운거": "HOT", "따뜻한거": "HOT", "핫": "HOT", "hot": "HOT",
    "차갑게": "COLD", "시원하게": "COLD", "차가운거": "COLD", "아이스": "COLD", "ice": "COLD", "cold": "COLD",
}
SERVICE_TYPES = {
    "매장": "DINE_IN", "매장에서": "DINE_IN", "매장에서마실게요": "DINE_IN", "먹고갈게요": "DINE_IN",
    "포장": "TAKEOUT", "포장해서": "TAKEOUT", "가져갈게요": "TAKEOUT", "테이크아웃": "TAKEOUT",
}
TASTE_PREFIXES = {
    "달지않은": ("sweetness", 0.2), "달콤한": ("sweetness", 0.8), "단": ("sweetness", 0.8),
    "시지않은": ("sourness", 0.2), "새콤한": ("sourness", 0.8),
    "쓰지않은": ("bitterness", 0.2), "쓴": ("bitterness", 0.8),
}
TASTE_CATEGORIES = {"커피": "coffee", "차": "tea", "티": "tea", "에이드": "ade", "라떼": "latte", "논커피라떼": "non_coffee_latte"}
ORDINALS = {"첫번째": 0, "두번째": 1, "세번째": 2, "네번째": 3, "1번": 0, "2번": 1, "3번": 2, "4번": 3}


def _compact(text: str) -> str:
    return "".join(char for char in normalize("NFKC", text).casefold() if char.isalnum())


def _recommendation(phrase: str) -> Recommend | None:
    phrase = phrase.removesuffix("추천해줘").removesuffix("추천")
    for prefix, (taste, target) in TASTE_PREFIXES.items():
        if phrase.startswith(prefix):
            category = phrase[len(prefix):]
            if category in {"", "음료", "거", "것"}:
                return Recommend(filters={}, targets={taste: target})
            if category in TASTE_CATEGORIES:
                return Recommend(filters={TASTE_CATEGORIES[category]: 1}, targets={taste: target})
    return None


def interpret_transcript(
    transcript: str,
    stage: VoiceStage,
    menus: dict[str, dict],
    *,
    selected_menu_id: str | None = None,
    candidate_menu_ids: tuple[str, ...] = (),
) -> VoiceAction:
    phrase = _compact(transcript)
    if not phrase:
        return Retry(reason="EMPTY_TRANSCRIPT")
    for ending in POLITE_ENDINGS:
        if phrase.endswith(ending):
            phrase = phrase.removesuffix(ending)
            break

    if stage in {"menu_confirmation", "review"}:
        return Confirm() if phrase in {"네", "예", "맞아요", "주문", "주문할게요", "주문확정", "확정"} else Retry(reason="UNRECOGNIZED")

    if stage in {"temperature", "service_type"}:
        menu = menus.get(selected_menu_id or "")
        if not menu or not menu["is_available"]:
            return Retry(reason="MENU_UNAVAILABLE")
        if stage == "temperature":
            temperature = TEMPERATURES.get(phrase)
            if temperature is None:
                return Retry(reason="UNRECOGNIZED")
            if temperature not in menu["available_temperatures"]:
                return Retry(reason="INVALID_OPTION")
            return SetTemperature(temperature=temperature)
        service_type = SERVICE_TYPES.get(phrase)
        return SetServiceType(service_type=service_type) if service_type else Retry(reason="UNRECOGNIZED")

    if stage == "recommendations" and phrase in ORDINALS:
        index = ORDINALS[phrase]
        if index >= len(candidate_menu_ids):
            return Retry(reason="OUTSIDE_CANDIDATES")
        matches = [candidate_menu_ids[index]]
    else:
        matches = [menu_id for menu_id, menu in menus.items() if _compact(menu["name"]) == phrase]
    if len(matches) != 1:
        return _recommendation(phrase) or Retry(reason="UNRECOGNIZED")
    menu_id = matches[0]
    if stage == "recommendations" and menu_id not in candidate_menu_ids:
        return Retry(reason="OUTSIDE_CANDIDATES")
    if not menus[menu_id]["is_available"]:
        return Retry(reason="MENU_UNAVAILABLE")
    return SelectMenu(menu_id=menu_id)
