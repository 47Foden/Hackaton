"""Narrow, auditable guards for v2; never a taste parser or ranker.

Unknown or contradictory hard constraints ask a question. This is not a complete
Korean NLU system, and the original transcript still goes to the selector.
"""
import re

DIGITS = dict(zip('일이삼사오육칠팔구', range(1, 10)))
UNITS = {'십': 10, '백': 100, '천': 1000}


def won_amount(value):
    if ',' in value and not re.fullmatch(r'\d{1,3}(?:,\d{3})+', value.strip()):
        raise ValueError('Malformed digit grouping')
    compact = value.replace(',', '').replace(' ', '')
    if re.fullmatch(r'\d+', compact):
        return int(compact)
    if re.fullmatch(r'\d+[천만]', compact):
        return int(compact[:-1]) * (1000 if compact[-1] == '천' else 10000)
    if compact == '만':
        return 10000
    if compact.endswith('만') and compact[:-1] in DIGITS:
        return DIGITS[compact[:-1]] * 10000
    if not compact or any(c not in DIGITS and c not in UNITS for c in compact):
        raise ValueError('Unsupported Korean amount')
    total, pending, previous = 0, 0, 10000
    for char in compact:
        if char in DIGITS:
            if pending:
                raise ValueError('Ambiguous Korean amount')
            pending = DIGITS[char]
        else:
            unit = UNITS[char]
            if unit >= previous:
                raise ValueError('Invalid unit order')
            total += (pending or 1) * unit
            pending, previous = 0, unit
    return total + pending


def derive_conditions(text):
    compact = re.sub(r'\s+', '', text)
    result = {'min_price_krw': None, 'max_price_krw': None, 'temperature': None,
              'excluded_categories': [], 'milk_free': False, 'max_caffeine_mg': None,
              'required_questions': [], 'unsupported_conditions': [], 'evidence_spans': []}
    money = list(re.finditer(r'(?P<amount>[\d,일이삼사오육칠팔구십백천만]+)\s*원\s*'
                             r'(?P<op>이하|미만|이상|초과|까지|한\s*장|한\s*장으로|(?:을|를)?\s*(?:넘지|넘기지)\s*않(?:는|게|도록)?)', text))
    for match in money:
        if re.match(r'\s*(?:는|은|가|이)?\s*(?:아니|아닌|말고)', text[match.end():]) or (match.start() and text[match.start()-1] == '-'):
            result['unsupported_conditions'].append('부정되거나 음수인 금액 조건')
            continue
        try:
            amount = won_amount(match['amount'])
        except ValueError:
            result['unsupported_conditions'].append('해석하지 못한 금액 표현')
            continue
        op = re.sub(r'\s+', '', match['op'])
        if op in ('이상', '초과'):
            value = amount + (op == '초과')
            result['min_price_krw'] = max(result['min_price_krw'] or 0, value)
        else:
            value = amount - (op == '미만')
            result['max_price_krw'] = min(result['max_price_krw'] if result['max_price_krw'] is not None else value, value)
        result['evidence_spans'].append({'field': 'price', 'text': match[0], 'start': match.start(), 'end': match.end()})
    if re.search(r'(?:\d|[일이삼사오육칠팔구십백천만])\s*원', text) and not money:
        result['unsupported_conditions'].append('금액은 있지만 이하/미만/이상/초과/한 장 조건이 명확하지 않음')
    if re.search(r'\d+\.\d+\s*[천만]?\s*원', text):
        result['unsupported_conditions'].append('소수점 금액 표현은 현재 지원하지 않음')
    if re.search(r'예산|저렴|싼|비싸지', compact) and not money:
        result['required_questions'].append('예산은 몇 원 이하인가요?')
    if (result['min_price_krw'] is not None and result['max_price_krw'] is not None
            and result['min_price_krw'] > result['max_price_krw']):
        result['unsupported_conditions'].append('가격 조건이 서로 충돌함')
    cold = bool(re.search(r'차갑|차가운|차게|시원|아이스', compact))
    hot = bool(re.search(r'뜨겁|뜨거운|따뜻|따듯|핫으로', compact))
    # Negated temperatures need confirmation rather than accidentally enforcing the opposite.
    if re.search(r'(?:차갑|차가운|차게|시원|아이스|뜨겁|뜨거운|따뜻|따듯).{0,5}(?:말고|싫|빼|않)', compact):
        result['required_questions'].append('원하는 온도가 HOT인가요, COLD인가요?')
    elif cold and hot:
        result['required_questions'].append('HOT과 COLD 중 어떤 온도를 원하시나요?')
    else:
        result['temperature'] = 'COLD' if cold else 'HOT' if hot else None
    keep_coffee = re.search(r'커피(?:는|가|를|만|은)?(?:빼지|제외하지)(?:말|마|않)', compact)
    if not keep_coffee and re.search(r'커피(?:는|가|를|만|은)?(?:말고|빼|제외|아닌|아니|안마셔|안먹|안돼|안되|싫어요|싫어)', compact):
        result['excluded_categories'].append('커피')
    keep_milk = re.search(r'우유.{0,4}(?:빼지|제외하지)(?:말|마|않)', compact)
    if not keep_milk and re.search(r'우유.{0,10}(?:빼|제외|없이|없는|싫어요|싫어|안들어|안돼|안되)|우유없는|무우유', compact):
        result['milk_free'] = True
    if re.search(r'카페인(?:은|이|을)?(?:없는|없이|없|빼|제외|0(?:\.0)?mg)|무카페인', compact, re.I):
        result['max_caffeine_mg'] = 0
    if re.search(r'디카페인|카페인.{0,5}(?:적|낮|덜)', compact) and result['max_caffeine_mg'] is None:
        result['required_questions'].append('카페인이 표기상 0mg인 음료를 원하시나요, 적은 양도 괜찮으신가요?')
    elif '카페인' in compact and result['max_caffeine_mg'] is None:
        result['required_questions'].append('원하는 카페인 기준을 알려주시겠어요? 표기 0mg을 원하시나요?')
    if re.search(r'밤|저녁|자기전|취침|수면', compact) and re.search(r'잠깨|잠이깨|잠못|잠안|잠을깨|각성', compact):
        result['required_questions'].append('커피 종류 제외와 카페인 회피는 달라요. 카페인 표기 0mg을 기준으로 고를까요? 수면 영향은 보장할 수 없어요.')
    if re.search(r'끈적|텁텁하지|뒷맛', compact):
        result['required_questions'].append('뒷맛 자료가 부족해요. 단맛이 약한 쪽을 원하시나요, 산미나 탄산이 있는 쪽을 원하시나요?')
    if re.search(r'알레르기|알러지', compact):
        result['unsupported_conditions'].append('전체 성분과 교차접촉 자료가 없어 알레르기 안전성을 확정할 수 없음')
    if result['unsupported_conditions']:
        result['required_questions'].append('조건을 정확히 확인할 수 있도록 금액·제외 성분·원하는 기준을 다시 알려주시겠어요?')
    result['required_questions'] = list(dict.fromkeys(result['required_questions']))
    return result
