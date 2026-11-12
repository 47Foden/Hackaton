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
_PATTERN = re.compile(
    r'(?<![가-힣a-zA-Z])(' + '|'.join(ORDER_ALIASES) +
    r')(?=$|[^가-힣a-zA-Z]|한|두|세|네|하나|주세요|줘|로|랑|하고|도|말고|에|는|만)'
)


def expand_order_aliases(text: str) -> str:
    return _PATTERN.sub(lambda m: ORDER_ALIASES[m[1]], normalize('NFKC', text))
