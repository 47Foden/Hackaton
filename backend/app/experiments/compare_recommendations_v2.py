"""v2 paired text runner; mock default, no credential file access in mock.

Server guards are recorded separately from model calls and quality measurements.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
from time import perf_counter

from app.experiments.compare_recommendations import CASES, digest
from app.experiments.menu_evidence import DEFAULT_EVIDENCE
from app.experiments.evaluate_recommendations_v2 import evaluate_record
from app.services import llm_direct_v2 as v2
from app.services.llm_direct import DirectError, openai_transport
from app.services.recommendation import recommend as existing_recommend
from app.services.sensory_tags import RESEARCHED_EVIDENCE
from app.experiments.recorded_transport import recorded_transport


def mock_transport(payload):
    """Fixed structural fixture, not a recommender and not a quality simulation."""
    result = {'status': 'insufficient_data', 'recommendations': [], 'questions': [],
              'missing_information': ['MOCK 고정 응답: 실제 추천 품질은 평가하지 않았습니다.']}
    return {'status': 'completed', 'model': 'mock-v2-fixture', 'usage': None,
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(result)}]}]}


def cost(usage, rates):
    if not rates or not usage:
        return None
    cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
    return ((usage['input_tokens'] - cached)*rates[0] + cached*rates[1] + usage['output_tokens']*rates[2])/1_000_000


def compare(menus, evidence, cases, repeat, model, transport, mode, candidate_mode='full', rates=None, decision_mode='llm'):
    records = []
    for case in cases:
        for run in range(1, repeat+1):
            row = {'case_id': case['id'], 'text': case['text'], 'repeat': run, 'methods': {}}
            start = perf_counter()
            try:
                baseline = {'status': 'ok', 'result': {'menu_ids': existing_recommend(case['text'], menus)}}
            except (ValueError, KeyError, OSError):
                baseline = {'status': 'error', 'error_code': 'EXISTING_INPUT_OR_DATA_ERROR'}
            baseline.update(latency_ms=round((perf_counter()-start)*1000, 3), usage=None, cost_usd_estimate=0)
            row['methods']['existing'] = baseline
            start = perf_counter()
            try:
                direct = v2.recommend(case['text'], menus, evidence, model, transport, candidate_mode, decision_mode)
                direct['status'] = 'ok'
            except DirectError as error:
                direct = {'status': 'error', 'error_code': str(error), 'usage': error.usage,
                          'rejected_response': error.candidate_response, 'api_calls': 1, 'origin': 'llm'}
            direct['transport_calls'] = direct['api_calls']
            if mode == 'mock' and direct['origin'] == 'llm':
                direct.update(origin='mock_fixture', api_calls=0)
            direct.update(latency_ms=round((perf_counter()-start)*1000, 3),
                          human_review={'condition_adherence': None, 'suitability': None, 'reason_accuracy': None})
            direct['cost_usd_estimate'] = 0 if direct['origin'] == 'server_guard' else cost(direct['usage'], rates)
            if 'evaluation' in case:
                direct['independent_evaluation'] = evaluate_record(direct, case, menus, evidence, mode)
            row['methods']['llm_direct_v2'] = direct
            records.append(row)
    consistency = {}
    for case in cases:
        successful = [r['methods']['llm_direct_v2'] for r in records
                      if r['case_id'] == case['id'] and r['methods']['llm_direct_v2']['status'] == 'ok']
        model_results = [d['result'] for d in successful if d['origin'] == 'llm']
        consistency[case['id']] = {'server_guard_runs': sum(d['origin'] == 'server_guard' for d in successful),
            'model_successful_runs': len(model_results),
            'identical_full_model_results': len({digest(x) for x in model_results}) == 1 if len(model_results) >= 2 else None,
            'quality_interpretation_allowed': mode == 'live'}
    return {'version': v2.PROMPT_VERSION, 'mode': mode, 'model': model, 'candidate_mode': candidate_mode, 'decision_mode': decision_mode,
            'rates_usd_per_million': rates, 'evidence_sha256': digest(evidence), 'menu_snapshot_sha256': digest(menus),
            'evaluation_annotations': {c['id']: c['evaluation'] for c in cases if 'evaluation' in c},
            'menu_snapshot': menus, 'cases_sha256': digest(cases), 'runs': records, 'consistency': consistency,
            'information_difference': 'Same transcript and base menu snapshot. V2 additionally receives structured facts, editorial sensory hypotheses (NOT ground truth), and deterministic guard hints. Default full/llm sends all menus and lets the model decide recommendation vs clarification. Server validates the response. Optional eligible/guarded modes are separate ablations, not a fallback to baseline. Human evaluation annotations are never read. Baseline remains original CSV/regex.',
            'limitations': ['Mock fixtures and deterministic guard answers are not model performance.',
                           'Guard parser supports limited explicit Korean forms; omissions and over-clarification remain possible.',
                           'Fact IDs check ownership/temperature; subjective suitability and free questions need review.',
                           'No automatic repair/retry and no score-based reranking. V1 results remain unchanged.']}


def save(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# v2 텍스트 실험', '', '**' + report['mode'] + '** / 후보 제공 방식: ' + report['candidate_mode'] + ' / 판단 주체: ' + report['decision_mode'], '',
             'mock 고정 응답과 서버의 질문/자료 보류는 LLM 추천 성능으로 세지 않습니다.',
             'v1보다 개선됐다는 판단은 동일 조건의 실제 API 비교와 사람 평가 이후에만 가능합니다.', '',
             '| 발화 | 기존 경로 | v2 경로 | 응답 주체 | API 호출 수 |', '|---|---|---|---|---|']
    for row in report['runs']:
        d = row['methods']['llm_direct_v2']
        status = d.get('result', {}).get('status', d.get('error_code', 'unknown'))
        lines.append(f"| {row['text']} | {row['methods']['existing']['status']} | {status} | {d['origin']} | {d['api_calls']} |")
    lines += ['', '## 질문과 추천 근거', '']
    for row in report['runs']:
        d = row['methods']['llm_direct_v2']
        lines += ['### ' + row['case_id'] + f" ({row['repeat']})", '',
                  '```json', json.dumps(d.get('result', {'error_code': d.get('error_code')}), ensure_ascii=False, indent=2), '```', '']
        if 'independent_evaluation' in d:
            lines += ['별도 조건 점검(주관적 추천 품질 점수 아님):', '',
                      '```json', json.dumps(d['independent_evaluation'], ensure_ascii=False, indent=2), '```', '']
        lines += ['지연(ms): ' + str(d['latency_ms']), 'usage: ' + json.dumps(d['usage'], ensure_ascii=False),
                  '비용 추정(USD): ' + str(d['cost_usd_estimate']), '']
    direct = [r['methods']['llm_direct_v2'] for r in report['runs']]
    known = sum(r['cost_usd_estimate'] for r in direct if r['cost_usd_estimate'] is not None)
    unknown = sum(r['api_calls'] > 0 and r['cost_usd_estimate'] is None for r in direct)
    lines += ['## 비용 및 한계', '', f'알려진 usage의 비용 추정 소계: USD {known:.8f}. 비용 미상 호출 {unknown}회.',
              '추정 단가는 JSON에 기록하며 실제 청구액과 다를 수 있습니다. 한 번씩 실행하므로 반복 일관성은 평가하지 못합니다.',
              '서버 검증 통과는 주관적인 추천 품질 통과가 아닙니다. mock이면 실제 모델 품질은 미평가입니다.']
    (directory/'results.ko.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--menus', type=Path, help='Same actual DB snapshot used for comparison; fixture status must be disclosed')
    source.add_argument('--v1-report', type=Path, help='Reuse only the recorded v1 catalogue, not its evaluation annotations')
    parser.add_argument('--evidence', type=Path, default=RESEARCHED_EVIDENCE)
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--candidate-mode', choices=('eligible', 'full'), default='full')
    parser.add_argument('--decision-mode', choices=('llm', 'guarded'), default='llm', help='Default: LLM chooses candidates and whether to ask a question')
    parser.add_argument('--mode', choices=('mock', 'live'), default='mock')
    parser.add_argument('--repeat', type=int, default=1)
    parser.add_argument('--max-api-calls', type=int, default=10, help='Hard per-run request count cap; no retries')
    parser.add_argument('--model', default='not-configured')
    parser.add_argument('--allow-paid-api', action='store_true')
    parser.add_argument('--env-file', type=Path, help='Only the key owner should run live with this option')
    parser.add_argument('--rates', nargs=3, type=float)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10:
        parser.error('--repeat must be 1..10')
    if not 1 <= args.max_api_calls <= 100:
        parser.error('--max-api-calls must be 1..100')
    if args.rates and any(not math.isfinite(x) or x < 0 for x in args.rates):
        parser.error('rates must be finite nonnegative values')
    if args.mode == 'live' and (not args.allow_paid_api or not args.env_file or args.model == 'not-configured'):
        parser.error('Live requires explicit --allow-paid-api --env-file --model; key owner runs personally')
    if (args.output_dir/'results.json').exists():
        parser.error('Results already exist; choose a new folder to preserve previous results')
    source_file = args.v1_report or args.menus
    raw = json.loads(source_file.read_text(encoding='utf-8-sig'))
    menus = raw['smoke']['catalog'] if args.v1_report else raw['menus'] if isinstance(raw, dict) else raw
    evidence = json.loads(args.evidence.read_text(encoding='utf-8-sig'))
    cases = json.loads(args.cases.read_text(encoding='utf-8-sig')) if args.cases else CASES
    if not cases or len({c['id'] for c in cases}) != len(cases):
        parser.error('Nonempty unique case IDs required')
    if args.mode == 'live' and len(cases)*args.repeat > args.max_api_calls:
        parser.error('Requested cases exceed --max-api-calls; no key was read or API called')
    journal = args.output_dir/'api-attempts.json'
    if args.mode == 'live' and journal.exists():
        parser.error('A paid attempt already exists here. Inspect api-attempts.json; do not repeat interrupted calls blindly.')
    # Validate all preparation before any credential access. Never read evaluator constraint hints.
    for case in cases:
        v2.prepare_context(case['text'], menus, evidence, args.candidate_mode, args.decision_mode)
    previous_key = os.environ.get('OPENAI_API_KEY')
    try:
        if args.mode == 'live':
            from app.experiments.run_small_experiment import load_user_key
            os.environ['OPENAI_API_KEY'] = load_user_key(args.env_file)
        transport = recorded_transport(openai_transport, journal, args.max_api_calls) if args.mode == 'live' else mock_transport
        report = compare(menus, evidence, cases, args.repeat, args.model, transport,
                         args.mode, args.candidate_mode, args.rates, args.decision_mode)
        report['max_api_calls'] = args.max_api_calls
        report['retries'] = 0
        report['input_file_sha256'] = hashlib.sha256(source_file.read_bytes()).hexdigest()
        report['catalog_source'] = 'recorded_v1_snapshot' if args.v1_report else 'explicit_menu_file'
        save(report, args.output_dir)
    finally:
        if previous_key is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = previous_key
    print('V2 report saved. Server guards are separate from model results; mock quality is unmeasured.')


if __name__ == '__main__':
    main()
