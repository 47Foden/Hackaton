"""Validate curated evidence and prepare requests offline. No network transport exists here."""
import argparse
from datetime import date
import json
import math
from pathlib import Path
from urllib.parse import urlparse

from app.db.catalog import load_catalog
from app.experiments.compare_recommendations import CASES
from app.services.llm_direct import build_request, validate_response

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_EVIDENCE = ROOT / 'common/experiments/llm_direct/menu_evidence.json'
FIELDS = ('description', 'caffeine_mg', 'milk', 'allergens')


def validate_evidence(data, catalog):
    by_id = {m.menu_id: m for m in catalog}
    if not isinstance(data, dict) or set(data) != {'schema_version', 'menus'} or data['schema_version'] != 1:
        raise ValueError('Invalid evidence schema')
    if not isinstance(data['menus'], list) or len(data['menus']) != len(by_id):
        raise ValueError('Evidence must cover all catalogue IDs, including unknowns')
    seen = set()
    for row in data['menus']:
        if set(row) != {'menu_id', 'name', 'official_name', 'mapping_note', 'variants'}:
            raise ValueError('Invalid menu evidence fields')
        mid = row['menu_id']
        if mid not in by_id or mid in seen or row['name'] != by_id[mid].name:
            raise ValueError('Unknown, duplicate or mismatched menu ID')
        seen.add(mid)
        if not all(isinstance(row[k], str) and row[k].strip() for k in ('official_name', 'mapping_note')):
            raise ValueError('Missing mapping information')
        temps = {t for t, _ in by_id[mid].variants}
        if set(row['variants']) != temps:
            raise ValueError('Evidence temperatures differ from catalogue')
        for temperature, fields in row['variants'].items():
            if set(fields) != set(FIELDS):
                raise ValueError('Missing evidence fields; use unknown explicitly')
            for field, record in fields.items():
                if not isinstance(record, dict) or set(record) != {'status', 'value', 'source', 'checked_date', 'note'}:
                    raise ValueError('Invalid evidence record')
                if not isinstance(record['note'], str):
                    raise ValueError('Invalid evidence note')
                if record['status'] == 'unknown':
                    if any(record[k] is not None for k in ('value', 'source', 'checked_date')):
                        raise ValueError('Unknown evidence must not carry asserted facts')
                    continue
                if record['status'] != 'verified':
                    raise ValueError('Unsupported evidence status')
                source = record['source']
                if not isinstance(source, str) or urlparse(source).scheme != 'https' or not urlparse(source).netloc:
                    raise ValueError('Verified evidence needs HTTPS provenance')
                try:
                    checked = date.fromisoformat(record['checked_date'])
                except (ValueError, TypeError):
                    raise ValueError('Invalid checked date') from None
                if checked > date.today():
                    raise ValueError('Evidence checked date is in the future')
                value = record['value']
                if field == 'description' and (not isinstance(value, str) or not value.strip()):
                    raise ValueError('Empty description')
                if field == 'caffeine_mg' and (type(value) not in (int, float) or not math.isfinite(value) or value < 0):
                    raise ValueError('Invalid caffeine amount')
                if field == 'milk' and type(value) is not bool:
                    raise ValueError('Milk must be explicit boolean or unknown')
                if field == 'allergens' and (not isinstance(value, list) or not value or
                        any(not isinstance(x, str) or not x.strip() for x in value)):
                    raise ValueError('Record explicit listed allergens; blank label is unknown')
    return data


def export_facts(data):
    """Keep variant scope in every statement; never copy facts across aliases or temperatures."""
    result = {}
    labels = {'description': '공식 설명 요약', 'caffeine_mg': '공식 표기 카페인(mg/기본 1회 제공)',
              'milk': '우유 포함 확인', 'allergens': '공식 표기 알레르기 성분(교차접촉 보장 아님)'}
    for row in data['menus']:
        facts = []
        for temperature, fields in row['variants'].items():
            for field, record in fields.items():
                if record['status'] != 'verified':
                    continue
                value = json.dumps(record['value'], ensure_ascii=False)
                facts.append({'text': f"[{temperature}에만 적용] {labels[field]}: {value}. {record['note']}",
                              'source': record['source'], 'checked_date': record['checked_date']})
        result[row['menu_id']] = facts
    return result


def readiness(data):
    rows = []
    for menu in data['menus']:
        for temperature, fields in menu['variants'].items():
            rows.append({'menu_id': menu['menu_id'], 'name': menu['name'], 'temperature': temperature,
                         'verified': [f for f in FIELDS if fields[f]['status'] == 'verified'],
                         'missing': [f for f in FIELDS if fields[f]['status'] == 'unknown']})
    return {'menu_count': len(data['menus']), 'variant_count': len(rows), 'variants': rows,
            'limitations': ['Price and temperatures are repository snapshots, not a current store guarantee.',
                           'Availability must come from DB; catalogue fixture availability is synthetic.',
                           'Blank allergen label is not proof of milk absence or allergy safety.',
                           'A reported 0mg caffeine value does not guarantee a person will sleep well.',
                           'Free-text facts do not unlock machine verification of ingredient exclusions.']}


def prepare(data, menus, cases, model):
    facts = export_facts(data)
    enriched = [{**m, 'verified_facts': facts.get(m['menu_id'], [])} for m in menus]
    # Human evaluation annotations stay outside the model input by default.
    requests = [{'case_id': c['id'], 'request': build_request(c['text'], enriched, model),
                 'server_constraints': c.get('constraints', {})} for c in cases]
    return enriched, requests


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence', type=Path, default=DEFAULT_EVIDENCE)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--menus', type=Path, help='Real DB/API menu snapshot')
    source.add_argument('--catalog-fixture', action='store_true', help='Offline fixture; ALL availability values are synthetic')
    parser.add_argument('--model', default='not-configured')
    parser.add_argument('--response', type=Path, help='Optional hand-written structured response; never treated as model output')
    parser.add_argument('--case-id', default=CASES[0]['id'])
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    catalog = load_catalog()
    data = validate_evidence(json.loads(args.evidence.read_text(encoding='utf-8-sig')), catalog)
    if args.catalog_fixture:
        menus = [{'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
                  'categories': list(m.categories), 'available_temperatures': [t for t, _ in m.variants],
                  'is_available': True} for m in catalog]
    else:
        raw = json.loads(args.menus.read_text(encoding='utf-8-sig'))
        menus = raw['menus'] if isinstance(raw, dict) else raw
    if {m['menu_id'] for m in menus} != {m.menu_id for m in catalog}:
        parser.error('Menu snapshot IDs must match the evidence catalogue')
    enriched, requests = prepare(data, menus, CASES, args.model)
    report = readiness(data)
    report.update(mode='offline-preparation', synthetic_availability=args.catalog_fixture, paid_calls=0,
                  quality_evaluation='not_performed', constraint_hints_sent_to_model=False)
    if args.response:
        case = next((c for c in CASES if c['id'] == args.case_id), None)
        if case is None:
            parser.error('Unknown case ID')
        try:
            validate_response(json.loads(args.response.read_text(encoding='utf-8-sig')), enriched, case.get('constraints'))
            report['manual_response_check'] = {'accepted': True, 'origin': 'handwritten_fixture_not_llm'}
        except ValueError as error:
            report['manual_response_check'] = {'accepted': False, 'error': str(error), 'origin': 'handwritten_fixture_not_llm'}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, value in [('menus.json', enriched), ('verified-facts.json', export_facts(data)),
                        ('requests-preview.json', requests), ('readiness.json', report),
                        ('cases-unassisted.json', [{**c, 'constraints': {}} for c in CASES])]:
        (args.output_dir / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# 메뉴 자료 준비 현황', '', '**API 호출 0회. 추천 품질 미평가.**', '',
             f"메뉴 {report['menu_count']}개 / 온도 조합 {report['variant_count']}개. 판매 여부 합성: {args.catalog_fixture}.", '',
             '| 메뉴 | 온도 | 확인 필드 | 미확인 필드 |', '|---|---|---|---|']
    lines.extend(f"| {r['name']} | {r['temperature']} | {', '.join(r['verified']) or '-'} | {', '.join(r['missing']) or '-'} |" for r in report['variants'])
    lines += ['', 'description=공식 설명 요약, caffeine_mg=공식 표기 카페인, milk=우유 포함 여부, allergens=표기된 알레르기 성분.', '',
              '미확인은 없음/0과 다르다. HOT 자료를 COLD로, 공식 레몬차 자료를 별칭 레몬티로 자동 복제하지 않는다.',
              'requests-preview.json은 전송 전 요청 미리보기다. cases-unassisted.json은 모델에 조건 정답 힌트를 주지 않는 비교용이다.']
    (args.output_dir / 'readiness.ko.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f"Offline preparation complete: {report['menu_count']} menus; paid API calls: 0.")


if __name__ == '__main__':
    main()
