"""Expand explicit café shorthand while retaining the original transcript for display."""
import re
from unicodedata import normalize

ORDER_ALIASES = {
    '아아': '아이스 아메리카노',
    '뜨아': '뜨거운 아메리카노',
    '아샷추': '아이스 복숭아 아이스티 샷 추가',
    '아카라': '아이스 카페라떼',
    '아바라': '아이스 바닐라라떼',
    '블요스': '블루베리요거트스무디',
    '망요스': '망고요거트스무디',
    '딸요스': '딸기요거트스무디',
}
# Explicitly observed STT confusions only. Do not fuzzy-match arbitrary short
# syllables (e.g. "아" or "아주") into a paid order.
ASR_ALIASES = {
    '아샤추': '아샷추',
    '아샤주': '아샷추',
}
_ALIASES = {**ORDER_ALIASES, **{heard: ORDER_ALIASES[target] for heard, target in ASR_ALIASES.items()}}
_PATTERN = re.compile(
    r'(?<![가-힣a-zA-Z])(' +
    '|'.join(r'\s*'.join(re.escape(char) for char in alias) for alias in sorted(_ALIASES, key=len, reverse=True)) +
    r')(?=$|[^가-힣a-zA-Z]|한|두|세|네|하나|주세요|줘|로|랑|하고|도|말고|에|는|만)'
)


def expand_order_aliases(text: str) -> str:
    normalized = normalize('NFKC', text)
    def expand(match):
        alias = re.sub(r'\s+', '', match[1])
        value = _ALIASES[alias]
        if value == ORDER_ALIASES['아샷추'] and re.match(
                r'\s*(?:는|은|를|을)?\s*(?:말고|빼고|아니고)', normalized[match.end():]):
            # Keep rejection adjacent to the menu, before implied shot options.
            return '복숭아 아이스티'
        return value
    return _PATTERN.sub(expand, normalized)
