"""Extract explicit Korean constraints; menu suitability remains an LLM decision.

This is a conservative guard, not a complete language understanding model.
Unspecified conditions stay unrestricted and unknown ingredients stay unknown.
"""
import re

DIGITS = dict(zip('일이삼사오육칠팔구', range(1, 10)))
UNITS = {'십': 10, '백': 100, '천': 1000}
COUNTS = {'한': 1, '하나': 1, '두': 2, '둘': 2, '세': 3, '셋': 3, '네': 4, '넷': 4,
          '다섯': 5, '여섯': 6, '일곱': 7, '여덟': 8, '아홉': 9, '열': 10}
COUNT = r'(?:[1-9][0-9]?|' + '|'.join(sorted(COUNTS, key=len, reverse=True)) + ')'
AMOUNT = r'(?:\d[\d,]*(?:천|만)?|[일이삼사오육칠팔구십백천만]+)'
MONEY = re.compile(rf'(?P<amount>{AMOUNT})\s*원')
CATEGORIES = ['논커피라떼', '디카페인', '아메리카노', '콜드브루', '에스프레소', '스무디', '프라페', '에이드', '라떼', '주스', '커피', '티']


def won_amount(value):
    if ',' in value and not re.fullmatch(r'\d{1,3}(?:,\d{3})+', value.strip()):
        raise ValueError('Malformed digit grouping')
    compact = value.replace(',', '').replace(' ', '')
    if re.fullmatch(r'\d+', compact): return int(compact)
    if re.fullmatch(r'\d+[천만]', compact): return int(compact[:-1]) * (1000 if compact[-1] == '천' else 10000)
    if compact == '만': return 10000
    if compact.endswith('만') and compact[:-1] in DIGITS: return DIGITS[compact[:-1]] * 10000
    if not compact or any(c not in DIGITS and c not in UNITS for c in compact):
        raise ValueError('Unsupported Korean amount')
    total, pending, previous = 0, 0, 10000
    for char in compact:
        if char in DIGITS:
            if pending: raise ValueError('Ambiguous Korean amount')
            pending = DIGITS[char]
        else:
            unit = UNITS[char]
            if unit >= previous: raise ValueError('Invalid unit order')
            total += (pending or 1) * unit
            pending, previous = 0, unit
    return total + pending


def category_matches(menu, category):
    """Use catalogue taxonomy, including its combined smoothie/juice category."""
    categories, name = menu['categories'], menu['name'].replace(' ', '')
    if category == '커피': return categories[0] in ('커피', '디카페인')
    if category == '라떼': return '라떼' in categories or '논커피라떼' in categories
    if category in ('주스', '스무디'): return '스무디/주스' in categories and category in name
    if category == '아메리카노': return '아메리카노' in name
    return category in categories


def derive_conditions(text):
    # Latest explicit correction scopes price parsing; other constraints stay in the full text.
    corrected = re.split(r'(?:^|[\s,.])(?:아니|아니요|아니다)[\s,]+', text)[-1]
    compact = re.sub(r'\s+', '', text)
    result = {'min_price_krw': None, 'max_price_krw': None, 'approx_price_krw': None,
              'temperature': None, 'included_categories': [], 'excluded_categories': [],
              'milk_free': False, 'max_caffeine_mg': None, 'requested_count': None,
              'order_quantity': None, 'total_budget_krw': None, 'sort_by': 'relevance',
              'required_options': [], 'preferences': [], 'flavors': [], 'excluded_flavors': [],
              'required_questions': [], 'unsupported_conditions': [], 'evidence_spans': []}
    def upper(value):
        result['max_price_krw'] = min(result['max_price_krw'] if result['max_price_krw'] is not None else value, value)
    def lower(value):
        result['min_price_krw'] = max(result['min_price_krw'] or 0, value)
    matches = list(MONEY.finditer(corrected))
    consumed = set()
    for i, match in enumerate(matches):
        if i in consumed: continue
        try:
            if corrected[:match.start()].rstrip().endswith(('-', '−')):
                raise ValueError('Negative amount')
            amount = won_amount(match['amount'])
        except ValueError:
            result['unsupported_conditions'].append('해석할 수 없는 금액 표현')
            continue
        suffix = re.sub(r'\s+', '', corrected[match.end():])
        suffix = re.sub(r'^(?:은|는|을|를)', '', suffix)
        parsed = True
        if i + 1 < len(matches) and suffix.startswith('에서') and '사이' in corrected[matches[i+1].end():]:
            consumed.add(i+1)
            try:
                if corrected[:matches[i+1].start()].rstrip().endswith(('-', '−')):
                    raise ValueError('Negative range endpoint')
                end_amount = won_amount(matches[i+1]['amount'])
            except ValueError:
                result['unsupported_conditions'].append('해석할 수 없는 금액 표현')
                continue
            lower(amount); upper(end_amount)
        elif suffix.startswith('대'):
            lower(amount); upper(amount + 999)
        elif re.match(r'미만|아래|안되는|(?:짜리)?보다(?:더)?(?:싼|저렴)', suffix): upper(amount - 1)
        elif re.match(r'이하|이내|까지|안으로|안에서|안(?:[,.!?]|$)|넘(?:으|기)?면안|(?:을|를)?넘(?:지|기지)않|한장', suffix): upper(amount)
        elif suffix.startswith('이상'): lower(amount)
        elif suffix.startswith('초과'): lower(amount + 1)
        elif re.match(r'정도|쯤|가량', suffix): result['approx_price_krw'] = amount; result['sort_by'] = 'closest_price'
        else: parsed = False
        if parsed:
            result['evidence_spans'].append({'field': 'price', 'text': match[0], 'start': match.start(), 'end': match.end()})
    if re.search(r'\d+\.\d+\s*[천만]?\s*원', corrected): result['unsupported_conditions'].append('소수점 금액 표현')
    if result['min_price_krw'] is not None and result['max_price_krw'] is not None and result['min_price_krw'] > result['max_price_krw']:
        result['unsupported_conditions'].append('가격 조건 충돌')
    if re.search(r'(?:제일|가장)(?:저렴|싼)|저렴한순|싼순', compact): result['sort_by'] = 'price_asc'
    if re.search(r'비싼순|가격높은순', compact): result['sort_by'] = 'price_desc'
    for match in re.finditer(rf'(?P<count>{COUNT})\s*(?P<unit>개|가지|종|잔)', text):
        word, unit = match['count'], match['unit']
        count = int(word) if word.isdigit() else COUNTS[word]
        if unit == '잔': result['order_quantity'] = count
        else: result['requested_count'] = count
    if result['requested_count'] is None and re.search(r'하나(?:만|추천|없|골라)|한잔', compact): result['requested_count'] = 1
    if result['order_quantity'] and result['order_quantity'] > 1:
        if re.search(r'합쳐|합해서|총|합계', compact):
            result['total_budget_krw'] = result['max_price_krw']; result['max_price_krw'] = None
        result['unsupported_conditions'].append('현재 주문은 한 메뉴·한 잔만 지원함')
    # Mark individual positive/negative temperature mentions, then honor the surviving positive one.
    temperatures = []
    for match in re.finditer(r'차갑|차가운|차게|시원|아이스|찬거|뜨겁|뜨거운|따뜻|따듯|뜨끈|핫으로', compact):
        tail = compact[match.end():match.end()+12]
        negated = bool(re.match(r'(?:게|은|한|것|거|음료)?(?:은|는|가|이)?(?:말고|싫|빼|않|불편)', tail))
        negated |= bool(re.match(r'(?:마시면|먹으면).{0,3}(?:불편|싫)', tail))
        if not negated: temperatures.append('COLD' if re.match(r'차|시원|아이스|찬', match[0]) else 'HOT')
    if len(set(temperatures)) == 1: result['temperature'] = temperatures[0]
    elif len(set(temperatures)) > 1: result['unsupported_conditions'].append('온도 조건 충돌')
    # A shared postfix can exclude more than one category: '커피도 차도 싫어요'.
    if re.search(r'커피도(?:차|티)도싫', compact): result['excluded_categories'] += ['커피', '티']
    remainder = compact
    for category in CATEGORIES:
        if category in ('커피', '라떼') and '논커피라떼' in remainder: continue
        token = '논커피라떼' if category == '논커피라떼' else category
        if token not in remainder: continue
        keep = re.search(re.escape(token) + r'.{0,3}(?:빼지|제외하지)(?:말|마|않)', remainder)
        negative = re.search(re.escape(token) + r'(?:는|가|를|만|은|도)?(?:말고|빼|제외|아닌|아니|안마셔|안먹|안돼|안되|못마|못먹|싫)', remainder)
        target = 'excluded_categories' if negative and not keep else 'included_categories'
        if category not in result['excluded_categories']: result[target].append(category)
    if re.search(r'차(?:종류|중에서|한잔)', compact) and '티' not in result['excluded_categories']: result['included_categories'].append('티')
    result['included_categories'] = list(dict.fromkeys(result['included_categories']))
    result['excluded_categories'] = list(dict.fromkeys(result['excluded_categories']))
    keep_milk = re.search(r'우유.{0,4}(?:빼지|제외하지)(?:말|마|않)', compact)
    result['milk_free'] = bool(not keep_milk and re.search(r'우유.{0,10}(?:빼|제외|없이|없는|싫|안들어|안돼|안되)|무우유', compact))
    if re.search(r'카페인(?:은|이|을)?(?:없는|없이|없|빼|제외|0(?:\.0)?mg)|무카페인', compact, re.I): result['max_caffeine_mg'] = 0
    for option in ('두유', '오트밀크', '아몬드밀크', '얼음많이', '얼음없이'):
        if option in compact: result['required_options'].append(option)
    for flavor in ('딸기', '레몬', '망고', '초콜릿', '과일'):
        # Scope exclusion to this flavor, not to a different flavor later in the sentence.
        # The latest mention permits an explicit correction: "레몬 말고, 아니 레몬으로".
        mentions = list(re.finditer(re.escape(flavor), compact))
        if not mentions: continue
        tail = compact[mentions[-1].end():]
        prefix = r'(?:맛|향)?(?:은|는|이|가|도|을|를)?'
        keep = re.match(prefix + r'(?:빼지|제외하지)(?:말|마|않)', tail)
        excluded = not keep and re.match(prefix + r'(?:말고|빼|제외|싫|없는|없이|아닌|아니고|아니라)', tail)
        result['excluded_flavors' if excluded else 'flavors'].append(flavor)
    for pattern, preference in [(r'쓴맛.{0,3}(?:약|덜|낮)|안쓴|쓰지않|씁쓰름한건싫', '쓴맛 낮음'),
                                (r'달지않|안달|덜달|많이달지', '단맛 낮음'),
                                (r'달달|달콤', '단맛 높음'), (r'새콤|상큼', '상큼함'),
                                (r'과일향', '과일향'), (r'걸쭉하지않', '묽은 식감')]:
        if re.search(pattern, compact): result['preferences'].append(preference)
    if re.search(r'알레르기|알러지', compact): result['unsupported_conditions'].append('검증된 전체 성분·교차접촉 자료 필요')
    if re.search(r'제일잘나|가장인기|판매량|인기순', compact): result['unsupported_conditions'].append('판매량 자료 없음')
    if re.search(r'그거있잖|그거그거', compact): result['unsupported_conditions'].append('추천 조건 또는 지칭 대상 없음')
    return result
