"""Shared menu definitions; prices must be supplied from the actual menu board."""
CATEGORIES = {
    '커피': ['아이스아메리카노', '에스프레소', '카페라떼'],
    '티': ['복숭아 아이스티', '레몬티', '유자차', '레몬차'],
    '에이드': ['레몬에이드', '청포도에이드'],
    '논커피라떼': ['딸기라떼', '녹차라떼'],
    '라떼': ['카페라떼', '딸기라떼', '녹차라떼'],
}
MENUS = ['복숭아 아이스티', '레몬티', '아이스아메리카노', '레몬에이드', '딸기라떼', '청포도에이드', '카페라떼', '레몬차', '유자차', '에스프레소', '녹차라떼']
BINARY_ATTRIBUTES = ['커피', '티', '에이드', '라떼', '논커피라떼']
TASTE_ATTRIBUTES = ['단맛', '신맛', '쓴맛']
ATTRIBUTES = BINARY_ATTRIBUTES + TASTE_ATTRIBUTES + ['가격']
PRICE_OPTIONS = [1500, 2000, 2900, 3000, 3300, 3500, 3700]
