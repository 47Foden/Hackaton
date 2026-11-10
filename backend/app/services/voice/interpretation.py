import re
from unicodedata import normalize

from app.schemas.voice import Confirm, Retry, SelectMenu, SetServiceType, SetTemperature, VoiceAction, VoiceStage
from app.services.voice.options import is_option_only, scalar, TEMPERATURE_ALIASES, SERVICE_ALIASES

POLITE_ENDINGS = ("으로해주세요", "로해주세요", "하나주세요", "한잔주세요", "해주실래요", "해주세요", "주세요", "부탁해요")
ORDINALS = {"첫번째": 0, "두번째": 1, "세번째": 2, "네번째": 3, "1번": 0, "2번": 1, "3번": 2, "4번": 3}


def _compact(text: str) -> str:
    return "".join(char for char in normalize("NFKC", text).casefold() if char.isalnum())


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
        confirmations = {"네", "예", "맞아요", "주문", "주문할게요", "주문확정", "확정"}
        confirmed = phrase in confirmations
        if stage == 'menu_confirmation':
            confirmed = confirmed or any(phrase.startswith(word) and is_option_only(phrase[len(word):])
                                         for word in confirmations)
        return Confirm() if confirmed else Retry(reason="UNRECOGNIZED")

    if stage in {"temperature", "service_type"}:
        menu = menus.get(selected_menu_id or "")
        if not menu or not menu["is_available"]:
            return Retry(reason="MENU_UNAVAILABLE")
        if stage == "temperature":
            temperature, _ = scalar(phrase, TEMPERATURE_ALIASES)
            if temperature is None:
                return Retry(reason="UNRECOGNIZED")
            if temperature not in menu["available_temperatures"]:
                return Retry(reason="INVALID_OPTION")
            return SetTemperature(temperature=temperature)
        service_type, _ = scalar(phrase, SERVICE_ALIASES)
        return SetServiceType(service_type=service_type) if service_type else Retry(reason="UNRECOGNIZED")

    number = re.fullmatch(r"([1-9][0-9]*)번", phrase)
    if stage == 'recommendations' and not number and phrase not in ORDINALS:
        ordinal = re.match(r'([1-9][0-9]*번|첫번째|두번째|세번째|네번째)', phrase)
        if ordinal and is_option_only(phrase[ordinal.end():]):
            phrase = ordinal.group()
            number = re.fullmatch(r'([1-9][0-9]*)번', phrase)
    if stage == "recommendations" and (phrase in ORDINALS or number):
        index = ORDINALS[phrase] if phrase in ORDINALS else int(number[1]) - 1
        if index >= len(candidate_menu_ids):
            return Retry(reason="OUTSIDE_CANDIDATES")
        matches = [candidate_menu_ids[index]]
    else:
        matches = [
            menu_id for menu_id, menu in menus.items()
            if _compact(menu["name"]) == phrase or (menu_id == "iced_americano" and phrase == "아이스아메리카노")
        ]
    if len(matches) != 1:
        # Preserve exact catalogue names before removing option clauses; never
        # select a menu from an arbitrary substring or a multi-menu comparison.
        matches = [menu_id for menu_id, menu in menus.items()
                   if _compact(menu['name']) in phrase
                   and is_option_only(phrase.replace(_compact(menu['name']), '', 1))]
        if len(matches) != 1:
            return Retry(reason="UNRECOGNIZED")
    menu_id = matches[0]
    if stage == "recommendations" and menu_id not in candidate_menu_ids:
        return Retry(reason="OUTSIDE_CANDIDATES")
    if not menus[menu_id]["is_available"]:
        return Retry(reason="MENU_UNAVAILABLE")
    return SelectMenu(menu_id=menu_id)
