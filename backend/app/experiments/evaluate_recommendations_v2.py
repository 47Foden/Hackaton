"""Independent factual checks using evaluator annotations, NEVER sent to a model.

Subjective fit and preferred actions are review prompts, not an accuracy oracle.
"""


def evaluate_result(value, case, menus, evidence):
    by_id = {m['menu_id']: m for m in menus}
    fields = {m['menu_id']: m['variants'] for m in evidence['menus']}
    criteria = case.get('evaluation', {})
    constraints = criteria.get('hard_constraints', {})
    violations = []
    if not isinstance(value, dict) or value.get('status') not in ('recommend', 'clarify', 'insufficient_data'):
        return {'factual_violations': ['INVALID_RESULT'], 'behavior_review_required': True}
    recs = value.get('recommendations', [])
    if not isinstance(recs, list):
        return {'factual_violations': ['INVALID_RECOMMENDATIONS'], 'behavior_review_required': True}
    seen = set()
    for rec in recs:
        if not isinstance(rec, dict) or not isinstance(rec.get('menu_id'), str):
            violations.append('INVALID_RECOMMENDATION')
            continue
        mid, temp = rec['menu_id'], rec.get('temperature')
        if mid not in by_id:
            violations.append('UNKNOWN_MENU_ID')
            continue
        if mid in seen:
            violations.append('DUPLICATE_MENU_ID')
        seen.add(mid)
        menu = by_id[mid]
        if not menu['is_available']:
            violations.append('UNAVAILABLE_MENU')
        if temp not in menu['available_temperatures']:
            violations.append('UNAVAILABLE_TEMPERATURE')
        if constraints.get('temperature') and temp != constraints['temperature']:
            violations.append('WRONG_TEMPERATURE')
        if 'max_price_krw' in constraints and menu['price_krw'] > constraints['max_price_krw']:
            violations.append('OVER_BUDGET')
        if 'min_price_krw' in constraints and menu['price_krw'] < constraints['min_price_krw']:
            violations.append('UNDER_MIN_PRICE')
        if set(menu['categories']) & set(constraints.get('excluded_categories', [])):
            violations.append('EXCLUDED_CATEGORY')
        facts = fields.get(mid, {}).get(temp, {})
        milk = facts.get('milk', {})
        if constraints.get('milk_free') and not (milk.get('status') == 'verified' and milk.get('value') is False):
            violations.append('MILK_NOT_VERIFIED_ABSENT')
        caffeine = facts.get('caffeine_mg', {})
        if 'max_caffeine_mg' in constraints and not (caffeine.get('status') == 'verified'
                and caffeine.get('value') <= constraints['max_caffeine_mg']):
            violations.append('CAFFEINE_NOT_VERIFIED_WITHIN_LIMIT')
    actions = criteria.get('preferred_actions', [])
    return {'factual_violations': sorted(set(violations)),
            'behavior_review_required': bool(actions and value['status'] not in actions),
            'expected_actions_for_review': actions, 'subjective_quality': None,
            'note': 'No factual violation does not prove preference fit or an appropriate question.'}


def evaluate_record(record, case, menus, evidence, mode):
    if mode != 'live':
        return {'state': 'not_scored_mock', 'factual_violations': None, 'subjective_quality': None}
    if record.get('origin') == 'server_guard':
        return {'state': 'server_guard_only_not_model_quality', 'factual_violations': None, 'subjective_quality': None}
    raw = record.get('result') or record.get('rejected_response')
    if raw is None:
        return {'state': 'no_parsed_response', 'factual_violations': None, 'subjective_quality': None}
    result = evaluate_result(raw, case, menus, evidence)
    result['state'] = 'raw_response_rejected_by_server' if record['status'] == 'error' else 'delivered_response_checked'
    return result
