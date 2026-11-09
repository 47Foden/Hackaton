"""Text-only paired runner. Default is an offline plumbing mock, never a quality benchmark."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from time import perf_counter

from app.services.llm_direct import (DirectError, PROMPT_VERSION, build_request,
                                     catalog_snapshot, direct_recommend, openai_transport)
from app.services.recommendation import recommend

CASES = [
    {'id': 'budget_no_coffee', 'text': '커피는 말고, 삼천 원 한 장으로 살 수 있는 거 있어요?',
     'constraints': {'max_price_krw': 3000, 'excluded_categories': ['커피']}},
    {'id': 'clean_finish', 'text': '입안이 텁텁한데 좀 깔끔하게 마실 만한 거 주세요.', 'constraints': {}},
    {'id': 'sweet_not_sticky', 'text': '달달한 건 좋은데, 먹고 나서 입이 끈적할 정도는 싫어요.', 'constraints': {}},
    {'id': 'no_milk', 'text': '우유 들어간 건 빼주세요. 대신 시큼한 건 괜찮아요.',
     'constraints': {'unverified_exclusions': ['우유']}},
    {'id': 'night_caffeine', 'text': '밤에 마실 거라 잠 깨는 건 싫은데, 커피만 아니면 되나요?',
     'constraints': {'unverified_exclusions': ['카페인/각성 영향']}},
]


def mock_transport(payload):
    """Fixed fixture; does not interpret the text or simulate recommendation ability."""
    result = {'status': 'insufficient_data', 'recommendations': [], 'questions': [],
              'missing_information': ['MOCK: 추천 성능 평가 불가. 확인된 맛·재료·카페인 자료 필요.']}
    return {'status': 'completed', 'model': 'mock-fixture', 'usage': None,
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(result)}]}]}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def compare(menus, cases, repeats, model, transport, mode, rates=None):
    snapshot = catalog_snapshot(menus)
    rows = []
    for case in cases:
        for repeat in range(repeats):
            pair = {'case_id': case['id'], 'text': case['text'], 'repeat': repeat + 1,
                    'constraints': case.get('constraints', {}), 'methods': {}}
            for method in ('existing', 'llm_direct'):
                started = perf_counter()
                record = {'status': 'ok', 'usage': None, 'cost_usd_estimate': None,
                          'human_review': {'condition_adherence': None, 'suitability': None,
                                           'reason_accuracy': None, 'notes': None}}
                try:
                    if method == 'existing':
                        record['result'] = {'menu_ids': recommend(case['text'], menus)}
                        record['cost_usd_estimate'] = 0  # Excludes historic Pretuning generation.
                    else:
                        record.update(direct_recommend(case['text'], menus, model, transport, case.get('constraints')))
                        record['automated_validation'] = 'passed_for_declared_constraints_only'
                        usage = record['usage']
                        if rates and usage:
                            cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
                            record['cost_usd_estimate'] = ((usage['input_tokens'] - cached) * rates[0]
                                + cached * rates[1] + usage['output_tokens'] * rates[2]) / 1_000_000
                except (DirectError, ValueError, OSError, KeyError) as error:
                    # Never serialize arbitrary exception text (provider body or local paths).
                    record.update(status='error', error_code=str(error) if isinstance(error, DirectError)
                                  else 'EXISTING_INPUT_OR_DATA_ERROR')
                    if isinstance(error, DirectError):
                        record['usage'] = error.usage
                        record['rejected_response'] = error.candidate_response
                        if rates and error.usage:
                            usage = error.usage
                            cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
                            record['cost_usd_estimate'] = ((usage['input_tokens'] - cached) * rates[0]
                                + cached * rates[1] + usage['output_tokens'] * rates[2]) / 1_000_000
                record['latency_ms'] = round((perf_counter() - started) * 1000, 3)
                pair['methods'][method] = record
            rows.append(pair)
    consistency = {}
    for case in cases:
        consistency[case['id']] = {}
        for method in ('existing', 'llm_direct'):
            records = [r['methods'][method] for r in rows if r['case_id'] == case['id']]
            successes = [r for r in records if r['status'] == 'ok']
            ids = [r['result'].get('menu_ids', [x['menu_id'] for x in r['result'].get('recommendations', [])]) for r in successes]
            consistency[case['id']][method] = {
                'successful_runs': len(successes), 'total_runs': len(records),
                'identical_ordered_ids': len({tuple(x) for x in ids}) == 1 if len(ids) >= 2 else None,
                'distinct_full_results': len({digest(r['result']) for r in successes}),
                'quality_interpretation_allowed': mode == 'live'}
    root = Path(__file__).resolve().parents[3]
    score_dir = root / 'common' / 'recommendation'
    return {'mode': mode, 'quality_warning': 'Mock results are plumbing checks, not recommendation performance.' if mode == 'mock' else None,
            'prompt_version': PROMPT_VERSION, 'requested_model': model,
            'catalog': snapshot, 'catalog_sha256': digest(snapshot), 'cases_sha256': digest(cases),
            'input_difference': {
                'shared': 'Same transcript and DB/file menu snapshot: ID, name, price, availability, temperatures.',
                'existing_only': 'Pretuning continuous/binary CSV, aliases, regex parser; no curated descriptions.',
                'llm_only': 'DB categories, curated verified_facts, system instructions and structured schema; no human condition hints.',
                'caveat': 'Case constraints are human annotations used only for server validation, never sent to the LLM. Baseline parser and ranking remain unchanged.',
                'score_sha256': {n: hashlib.sha256((score_dir / n).read_bytes()).hexdigest()
                                 for n in ('continuous.csv', 'binary.csv')},
                'request_example': build_request(cases[0]['text'], menus, model, cases[0].get('constraints'))},
            'cost_rates_usd_per_million': rates, 'consistency': consistency, 'runs': rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--menus', type=Path, help='Explicit snapshot JSON list or /api/menus response; availability must be real for a live benchmark')
    parser.add_argument('--facts', type=Path, help='Curated JSON menu_id -> [{text,source,checked_date}]')
    parser.add_argument('--cases', type=Path, help='JSON [{id,text,constraints}]; defaults to five requested utterances')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--mode', choices=('mock', 'live'), default='mock')
    parser.add_argument('--allow-paid-api', action='store_true')
    parser.add_argument('--model', default='not-configured')
    parser.add_argument('--rates', type=float, nargs=3, metavar=('INPUT', 'CACHED_INPUT', 'OUTPUT'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.repeat < 1 or args.repeat > 100:
        parser.error('--repeat must be 1..100')
    if args.rates and any(not math.isfinite(x) or x < 0 for x in args.rates):
        parser.error('rates must be finite nonnegative USD per million tokens')
    if args.mode == 'live' and (not args.allow_paid_api or args.model == 'not-configured'):
        parser.error('live requires --allow-paid-api and an explicitly chosen --model')
    if args.menus:
        data = json.loads(args.menus.read_text(encoding='utf-8-sig'))
        menus = data['menus'] if isinstance(data, dict) else data
        source = {'type': 'explicit_file', 'availability_caveat': 'Operator must verify snapshot freshness; not re-fetched per recommendation.'}
    else:
        from app.repositories.menus import list_menus
        menus = list_menus()
        source = {'type': 'database', 'availability_caveat': 'Single consistent snapshot, not order-time validation.'}
    if args.facts:
        facts = json.loads(args.facts.read_text(encoding='utf-8-sig'))
        if set(facts) - {m['menu_id'] for m in menus}:
            parser.error('facts contain unknown menu IDs')
        menus = [{**m, 'verified_facts': facts.get(m['menu_id'], [])} for m in menus]
    cases = json.loads(args.cases.read_text(encoding='utf-8-sig')) if args.cases else CASES
    if not cases or len({c['id'] for c in cases}) != len(cases):
        parser.error('case IDs must be unique and cases nonempty')
    report = compare(menus, cases, args.repeat, args.model,
                     openai_transport if args.mode == 'live' else mock_transport, args.mode, args.rates)
    report['catalog_source'] = source
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"{args.mode}: {len(report['runs'])} paired runs saved. Human quality review remains pending.")


if __name__ == '__main__':
    main()
