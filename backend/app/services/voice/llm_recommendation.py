"""V3 candidate selection for the current catalogue; never reads taste CSVs."""
import json
import os
from pathlib import Path

from app.db.catalog import load_catalog
from app.experiments.menu_evidence import validate_evidence
from app.services import llm_direct_v3 as v3
from app.services.llm_direct import DirectError, catalog_snapshot, openai_transport
from app.services.recommendation_conditions_v2 import derive_conditions

ROOT = Path(__file__).resolve().parents[4]
DEFAULT_EVIDENCE = ROOT/'common/experiments/llm_direct/menu_evidence_45.json'


def prepare_context(text, menus, evidence):
    if not isinstance(text, str) or not text.strip() or len(text) > 4000:
        raise DirectError('INVALID_TEXT')
    validate_evidence(evidence, load_catalog())
    snapshot = catalog_snapshot(menus)
    rows = {row['menu_id']: row for row in evidence['menus']}
    if set(rows) != {m['menu_id'] for m in snapshot}:
        raise DirectError('CATALOG_ID_MISMATCH')
    guard = derive_conditions(text)
    visible, facts, allowed = [], {}, {}
    for menu in snapshot:
        mid = menu['menu_id']
        variants = []
        allowed[mid] = []
        for temp in menu['available_temperatures']:
            fields = rows[mid]['variants'].get(temp)
            if fields is None: raise DirectError('EVIDENCE_TEMPERATURE_MISMATCH')
            ids, unknown = [], []
            for field, value in [('price_krw', menu['price_krw']), ('temperature', temp)]:
                fid = f'{mid}:{temp}:{field}'
                facts[fid] = {'menu_id': mid, 'temperature': temp, 'field': field, 'value': value,
                              'source': 'current_database_snapshot', 'checked_date': None}
                ids.append(fid)
            for field, record in fields.items():
                if record['status'] == 'unknown': unknown.append(field); continue
                fid = f'{mid}:{temp}:{field}'
                facts[fid] = {'menu_id': mid, 'temperature': temp, 'field': field, **record}
                ids.append(fid)
            good = menu['is_available'] and not (set(menu['categories']) & set(guard['excluded_categories']))
            good &= guard['max_price_krw'] is None or menu['price_krw'] <= guard['max_price_krw']
            good &= guard['min_price_krw'] is None or menu['price_krw'] >= guard['min_price_krw']
            good &= guard['temperature'] is None or temp == guard['temperature']
            if guard['milk_free']:
                good &= fields['milk']['status'] == 'verified' and fields['milk']['value'] is False
            if guard['max_caffeine_mg'] is not None:
                good &= fields['caffeine_mg']['status'] == 'verified' and fields['caffeine_mg']['value'] <= guard['max_caffeine_mg']
            if good: allowed[mid].append(temp)
            variants.append({'temperature': temp, 'fact_ids': ids, 'unknown_fields': unknown})
        visible.append({k: menu[k] for k in ('menu_id', 'name', 'price_krw', 'is_available', 'categories')} | {'variants': variants})
    return {'transcript': text, 'menus': visible, 'facts': facts, 'guard': guard, 'allowed': allowed,
            'decision_mode': 'llm', 'known_names': {m['menu_id']: {m['name']} for m in snapshot},
            'sensory': {'annotations': {}, 'definitions': {}}}


def recommend(text, menus, transport=None, evidence=None, model=None):
    if evidence is None:
        path = Path(os.environ.get('LLM_MENU_EVIDENCE_FILE', DEFAULT_EVIDENCE))
        evidence = json.loads(path.read_text(encoding='utf-8'))
    model = model or os.environ.get('LLM_RECOMMENDATION_MODEL', 'gpt-5.4-mini-2026-03-17')
    context = prepare_context(text, menus, evidence)
    request = v3.build_request(context, model)
    if model.startswith('gpt-5.4-mini'): request['reasoning'] = {'effort': 'none'}
    envelope, candidate = None, None
    try:
        envelope = (transport or openai_transport)(request)
        if envelope.get('status') != 'completed': raise DirectError('INCOMPLETE_RESPONSE')
        content = [c for item in envelope.get('output', []) if item.get('type') == 'message' for c in item.get('content', [])]
        if any(c.get('type') == 'refusal' for c in content): raise DirectError('PROVIDER_REFUSAL')
        parts = [c['text'] for c in content if c.get('type') == 'output_text']
        if len(parts) != 1: raise DirectError('INVALID_RESPONSE')
        candidate = json.loads(parts[0])
        return {'result': v3.validate_response(candidate, context), 'usage': envelope.get('usage'),
                'model': envelope.get('model', model)}
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        safe = error if isinstance(error, DirectError) else DirectError('INVALID_RESPONSE')
        safe.candidate_response = candidate
        safe.usage = envelope.get('usage') if isinstance(envelope, dict) else None
        raise safe from None
