"""Conservative evidence checks, not a numeric taste model or menu ranker."""
import re

SWEET = r'달콤|달달|달큰|단\s*맛|흑당|꿀|연유|시럽|대체당'
SOUR = r'상큼|새콤|신맛|산미|시트러스'
FRUIT = r'과일|복숭아|레몬|딸기|포도|자몽|유자|사과|망고|바나나|베리|키위|파인애플'
FLAVORS = {'과일': FRUIT, '초콜릿': r'초콜릿|초코', '딸기': r'딸기', '레몬': r'레몬', '망고': r'망고'}


def requires_description(guard):
    return bool(guard['preferences'] or guard['flavors'] or guard.get('excluded_flavors'))


def positive_terms(pattern, description):
    """Absence of a cue means insufficient support, never proof a taste is absent."""
    terms = []
    compact = re.sub(r'\s+', '', description)
    for match in re.finditer(pattern.replace(r'\s*', ''), compact):
        before, after = compact[max(0, match.start()-3):match.start()], compact[match.end():match.end()+10]
        if before.endswith(('안', '덜', '없이')) or re.match(r'(?:함|한|게|이|은|을|를|하|지)*(?:없|않|낮|줄|적|안|제외)', after):
            continue
        terms.append(match[0])
    return terms


def supports_request(guard, fields):
    if not requires_description(guard): return True
    record = fields['description']
    if record['status'] != 'verified': return False
    description = record['value']
    if any(positive_terms(FLAVORS[flavor], description)
           for flavor in guard.get('excluded_flavors', []) if flavor in FLAVORS):
        return False
    preferences = guard['preferences']
    if '단맛 높음' in preferences and '단맛 낮음' not in preferences and not positive_terms(SWEET, description):
        return False
    if '단맛 낮음' in preferences and positive_terms(SWEET, description):
        return False
    if '상큼함' in preferences and not positive_terms(SOUR, description):
        return False
    if any(not positive_terms(FLAVORS[flavor], description) for flavor in guard['flavors'] if flavor in FLAVORS):
        return False
    return True


def supports_caffeine_avoidance(menu, fields):
    """Offer decaf and non-coffee alternatives, never a numeric zero guarantee."""
    if menu['categories'][0] == '디카페인':
        return True
    caffeine = fields['caffeine_mg']
    if caffeine['status'] == 'verified':
        return caffeine['value'] == 0
    if menu['categories'][0] != '음료':
        return False
    description = fields['description']
    if description['status'] != 'verified':
        return False
    # Known caffeine-bearing bases disqualify a non-coffee alternative.
    text = menu['name'] + description['value']
    return not re.search(r'커피|에스프레소|콜드브루|홍차|녹차|말차|우롱|얼그레이|블랙티|초코|코코아|카카오|카페인', text)
