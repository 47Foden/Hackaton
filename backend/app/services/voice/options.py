"""Conservative, catalogue-backed option extraction independent of LLM suggestions."""

import os
import re
from functools import lru_cache
from pathlib import Path
from unicodedata import normalize

from app.db.catalog import ROOT, load_option_profiles
from app.schemas.voice import CustomizationIntent, RecognizedCustomization, RecognizedOptions


def compact(text: str) -> str:
    return ''.join(c for c in normalize('NFKC', text).casefold() if c.isalnum())


TEMPERATURE_ALIASES = {
    **dict.fromkeys(('뜨겁게', '따뜻하게', '뜨거운', '따뜻한', '핫', 'hot'), 'HOT'),
    **dict.fromkeys(('차갑게', '시원하게', '차가운', '시원한', '아이스', 'ice', 'cold'), 'COLD'),
}
SERVICE_ALIASES = {
    **dict.fromkeys(('매장에서마실게요', '매장에서', '매장', '먹고갈게요'), 'DINE_IN'),
    **dict.fromkeys(('포장해서', '포장', '가져갈게요', '테이크아웃'), 'TAKEOUT'),
}
NO_OPTIONS = ('추가옵션없이', '옵션없이', '추가옵션없음')


@lru_cache(maxsize=4)
def option_aliases(common_dir: str) -> dict[str, set[str]]:
    aliases: dict[str, set[str]] = {}
    for groups in load_option_profiles(Path(common_dir)).values():
        for group in groups:
            for choice in group['choices']:
                aliases.setdefault(compact(choice['label']), set()).add(choice['id'])
    for label, ids in list(aliases.items()):
        if '2샷' in label:
            aliases.setdefault(label.replace('2샷', '두샷'), set()).update(ids)
        if '샷추가' in label:
            aliases.setdefault(label.replace('샷추가', '샷하나추가'), set()).update(ids)
            aliases.setdefault(label.replace('샷추가', '샷도추가'), set()).update(ids)
        if '시럽추가' in label:
            aliases.setdefault(label.removesuffix('추가'), set()).update(ids)
            aliases.setdefault(label.replace('시럽추가', '시럽도추가'), set()).update(ids)
    aliases['휘핑빼고'] = {'whip:without'}
    return aliases


def matches(text: str, aliases: dict):
    pattern = '|'.join(re.escape(key) for key in sorted(aliases, key=len, reverse=True))
    return list(re.finditer(pattern, text)) if pattern else []


def is_rejected(text: str, match, following: int) -> bool:
    # A later correction of another field must not negate this selection.
    return re.match(r'(?:(?:으로|로|은|는|이|가|거|것|요|해주세요))*말고',
                    text[match.end():following]) is not None


def scalar(text: str, aliases: dict):
    found = matches(text, aliases)
    values = set()
    ambiguous = False
    for index, match in enumerate(found):
        end = found[index + 1].start() if index + 1 < len(found) else len(text)
        if is_rejected(text, match, end):
            continue
        if text[max(0, match.start() - 1):match.start()] == '안' or re.match(
            r'(?:하지않|하지말|아니|말|싫|않|안|이나|또는|은?거?말고)', text[match.end():end]
        ):
            ambiguous = True
        else:
            values.add(aliases[match.group()])
    if len(values) == 1 and not ambiguous:
        return next(iter(values)), False
    return None, bool(found)


def without_options(text: str) -> str:
    """Used only to recognize a direct menu/confirmation plus known option clauses."""
    aliases = option_aliases(str(Path(os.environ.get('COMMON_DIR', ROOT / 'common'))))
    combined = {**aliases, **TEMPERATURE_ALIASES, **SERVICE_ALIASES, **dict.fromkeys(NO_OPTIONS)}
    for match in reversed(matches(text, combined)):
        text = text[:match.start()] + text[match.end():]
    return text


def is_option_only(text: str) -> bool:
    # Do not accept arbitrary remainder (e.g. another menu, a negation or preference).
    remainder = without_options(text)
    return re.fullmatch(r'(?:(?:으로|로|하고|도|랑|과|와|은|는|을|를|한잔|하나|거|이요|요|해주세요|주세요|해주실래요|부탁해요|해|해서|할게요))*', remainder) is not None


def extract_options(transcript: str, *, menu: dict | None = None,
                    temperature: str | None = None) -> RecognizedOptions | None:
    text = compact(transcript)
    result = RecognizedOptions()
    for field, aliases in (('temperature', TEMPERATURE_ALIASES), ('service_type', SERVICE_ALIASES)):
        value, unresolved = scalar(text, aliases)
        if field == 'temperature' and value and menu and value not in menu['available_temperatures']:
            value, unresolved = None, True
        setattr(result, field, value)
        if unresolved:
            result.unresolved_fields.append(field)

    # Menu names can themselves contain e.g. whipped cream or syrup names.
    custom_text = text.replace(compact(menu['name']), '', 1) if menu else text
    aliases = option_aliases(str(Path(os.environ.get('COMMON_DIR', ROOT / 'common'))))
    found = matches(custom_text, aliases)
    intents = []
    unresolved = []
    covered = list(custom_text)
    for index, match in enumerate(found):
        covered[match.start():match.end()] = ' ' * (match.end() - match.start())
        end = found[index + 1].start() if index + 1 < len(found) else len(custom_text)
        if is_rejected(custom_text, match, end):
            continue
        if (re.search(r'[0-9한두세네]$', custom_text[:match.start()]) and '샷' in match.group()
                or re.match(r'(?:이나|나|또는)', custom_text[match.end():end])):
            unresolved.append(custom_text[max(0, match.start() - 1):match.end()])
            continue
        if (custom_text[max(0, match.start() - 1):match.start()] == '안'
                or re.match(r'(?:하지않|하지말|아니|싫|말|않|안|빼|없이)', custom_text[match.end():end])):
            unresolved.append(match.group())
            continue
        intents.append(CustomizationIntent(expression=match.group(), candidate_option_ids=sorted(aliases[match.group()])))
    # Unsupported quantities and unspecified syrup types must never disappear.
    remainder = ''.join(covered)
    unresolved.extend(m.group() for m in re.finditer(r'(?:\d+|한|두|세|네)?샷|시럽', remainder))
    explicit_none = any(word in custom_text for word in NO_OPTIONS)
    if explicit_none and (intents or unresolved):
        unresolved.append('추가 옵션 없음과 옵션 지정 충돌')
    if intents or unresolved or explicit_none:
        customization = RecognizedCustomization(status='pending', intents=intents, unresolved=unresolved)
        selected_temperature = result.temperature or temperature
        if menu and not selected_temperature and len(menu['available_temperatures']) == 1:
            selected_temperature = menu['available_temperatures'][0]
        if explicit_none and not intents and not unresolved:
            customization.status = 'resolved'
        elif menu and selected_temperature and 'temperature' not in result.unresolved_fields:
            groups = next((v.get('option_groups', []) for v in menu.get('variants', [])
                           if v['temperature'] == selected_temperature), [])
            available = {c['id'] for g in groups for c in g['choices']}
            for intent in intents:
                ids = available.intersection(intent.candidate_option_ids)
                if len(ids) != 1:
                    customization.unresolved.append(intent.expression)
                else:
                    option_id = next(iter(ids))
                    if option_id in customization.option_ids:
                        customization.unresolved.append('중복 옵션: ' + intent.expression)
                    else:
                        customization.option_ids.append(option_id)
            for group in groups:
                ids = {c['id'] for c in group['choices']}.intersection(customization.option_ids)
                if len(ids) > group['max_selections']:
                    customization.unresolved.append('선택 개수 초과: ' + group['id'])
                    customization.option_ids = [i for i in customization.option_ids if i not in ids]
            customization.status = 'resolved'
        if customization.unresolved:
            customization.status = 'needs_clarification'
        result.customization = customization
    return result if (result.temperature or result.service_type or result.customization or result.unresolved_fields) else None
