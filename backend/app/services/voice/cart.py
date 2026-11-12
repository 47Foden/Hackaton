"""Extract explicit named order lines; recommendations remain on their own path."""
import re
from app.schemas.voice import Retry, SelectMenu, VoiceCart, VoiceCartItem, VoiceAction
from app.services.voice.options import compact, extract_options, TEMPERATURE_ALIASES as TEMPERATURES


def find_menu_mentions(phrase: str, menus: dict[str, dict], *,
                       include_order_aliases: bool = False) -> list[tuple[int, int, str]]:
    names = [(compact(menu["name"]), key) for key, menu in menus.items()]
    if include_order_aliases and "cafe_latte" in menus:
        names.append(("라떼", "cafe_latte"))
    names.sort(key=lambda entry: -len(entry[0]))
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
    return found


QUANTITY = re.compile(r"(\d+|하나|한|둘|두|셋|세|넷|네|다섯|여섯)(?:잔|개)")
EXCLUSION = re.compile(r"(?:(?:은|는|을|를)|(?:\d+|한|두|세|네)(?:잔|개))?(?:말고|빼고|아니고)")


def is_suggestion(phrase: str) -> bool:
    return any(word in phrase for word in ("추천", "뭐가", "어떤"))


def ordered_mentions(phrase: str, mentions: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    ordered = []
    for index, mention in enumerate(mentions):
        stop = mentions[index + 1][0] if index + 1 < len(mentions) else len(phrase)
        suffix = phrase[mention[1]:stop]
        if EXCLUSION.match(suffix) and not has_quantity_correction(suffix):
            continue
        if index + 1 < len(mentions):
            separator = QUANTITY.sub("", suffix, count=1)
            if re.match(r"(?:이나|또는|혹은|아니면)", separator) or (
                separator.startswith("나") and (not separator[1:] or separator[1:] in TEMPERATURES)
            ):
                return []
        ordered.append(mention)
    return ordered


def interpret_named_order(text: str, menus: dict[str, dict], *,
                          candidate_menu_ids: tuple[str, ...] = ()) -> VoiceAction | None:
    phrase = compact(text)
    mentions = find_menu_mentions(phrase, menus, include_order_aliases=True)
    if not mentions:
        return None  # Keep the existing ordinal and retry handling.
    found = ordered_mentions(phrase, mentions)
    if not found or len(found) > 20 or is_suggestion(phrase):
        return Retry(reason="UNRECOGNIZED")
    if candidate_menu_ids and any(key not in candidate_menu_ids for _, _, key in found):
        return Retry(reason="OUTSIDE_CANDIDATES")
    if any(not menus[key]["is_available"] for _, _, key in found):
        return Retry(reason="MENU_UNAVAILABLE")
    if len(found) == 1:
        _, end, key = found[0]
        stop = next((start for start, _, _ in mentions if start >= end), len(phrase))
        if read_quantity(phrase[end:stop]) == 1:
            return SelectMenu(menu_id=key)
    cart = build_cart(phrase, menus, found, mentions, keep_unsupported_temperature=True)
    if cart is None:
        return Retry(reason="INVALID_OPTION")
    return cart


def parse_cart(text, menus):
    phrase = compact(text)
    mentions = find_menu_mentions(phrase, menus)
    found = ordered_mentions(phrase, mentions)
    if not found or len(found) > 20 or is_suggestion(phrase):
        return None
    if len(found) == 1 and phrase == compact(menus[found[0][2]]["name"]):
        return None
    return build_cart(phrase, menus, found, mentions)


def quantity_sequence(suffix: str):
    """Follow explicit corrections within a single menu's clause only."""
    matches = list(QUANTITY.finditer(suffix))
    if not matches:
        return []
    sequence = [matches[0]]
    for match in matches[1:]:
        between = suffix[sequence[-1].end():match.start()]
        if not re.fullmatch(r'(?:은|는|이|가|으로|로)?(?:말고|아니고|아니라|아니|대신)(?:요)?', between):
            break
        sequence.append(match)
    return sequence


def has_quantity_correction(suffix: str) -> bool:
    sequence = quantity_sequence(suffix)
    return len(sequence) > 1 and sequence[0].start() == 0


def read_quantity(suffix: str) -> int:
    sequence = quantity_sequence(suffix)
    if not sequence:
        return 1
    count = sequence[-1][1]
    counts = {"한": 1, "하나": 1, "두": 2, "둘": 2, "세": 3, "셋": 3, "네": 4, "넷": 4, "다섯": 5, "여섯": 6}
    return counts[count] if count in counts else int(count)


def build_cart(phrase, menus, found, mentions, *, keep_unsupported_temperature=False):
    lines = []
    for i, (start, end, key) in enumerate(mentions):
        if (start, end, key) not in found:
            continue
        menu = menus[key]
        if not menu["is_available"]:
            return None
        stop = mentions[i+1][0] if i+1 < len(mentions) else len(phrase)
        suffix = phrase[end:stop]
        prefix = phrase[:start] if i == 0 else phrase[mentions[i-1][1]:start]
        # Prefix temperature belongs to the menu immediately following it.
        temperatures = [(prefix.rfind(word), value) for word, value in TEMPERATURES.items() if prefix.endswith(word)]
        temperature = max(temperatures)[1] if temperatures else None
        if temperature and temperature not in menu["available_temperatures"] and not keep_unsupported_temperature:
            return None
        quantity = read_quantity(suffix)
        if not 1 <= quantity <= 99:
            return None
        variants = [v for v in menu.get("variants", []) if temperature is None or v["temperature"] == temperature]
        option_ids = []
        for variant in variants:
            for group in variant.get("option_groups", []):
                remaining = suffix
                for choice in sorted(group["choices"], key=lambda c: -len(compact(c["label"]))):
                    label = compact(choice["label"])
                    if label and label in remaining and choice["id"] not in option_ids:
                        option_ids.append(choice["id"])
                        remaining = remaining.replace(label, "", 1)
        recognized = extract_options(suffix, menu=menu, temperature=temperature)
        if recognized:
            # The suffix may end with the next menu's temperature prefix.
            # Only customization belongs to this line; scalars are scoped elsewhere.
            recognized.temperature = None
            recognized.service_type = None
            recognized.unresolved_fields = []
        if recognized and recognized.customization:
            custom = recognized.customization
            option_ids = custom.option_ids or [
                intent.candidate_option_ids[0] for intent in custom.intents
                if len(intent.candidate_option_ids) == 1]
        lines.append(VoiceCartItem(menu_id=key, temperature=temperature, quantity=quantity,
                                   option_ids=option_ids, recognized_options=recognized))
    return VoiceCart(items=lines)
