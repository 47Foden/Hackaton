"""Five easy cases, one call each. Mock default; live is run only by the key owner."""
import argparse
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from app.experiments.compare_recommendations_v2 import cost
from app.experiments.evaluate_recommendations_v2 import evaluate_record
from app.experiments.recorded_transport import recorded_transport
from app.services import llm_direct_v3 as v3
from app.services.llm_direct import DirectError, openai_transport
from app.services.recommendation import recommend as existing_recommend
from app.services.sensory_tags import RESEARCHED_EVIDENCE, ROOT

CASES_PATH = ROOT/'common/experiments/llm_direct/v3_easy_cases.json'


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def mock_transport(payload):
    value = {'status': 'insufficient_data', 'requested_menu_name': '', 'recommendations': [],
             'questions': [], 'unresolved_requirements': [],
             'missing_information': ['고정 mock 응답. 실제 추천 품질은 측정하지 않음.']}
    return {'status': 'completed', 'usage': None,
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


def check_easy(record, case, menus, evidence, mode):
    factual = evaluate_record(record, case, menus, evidence, mode)
    if mode != 'live':
        return {'factual_check': factual, 'narrow_case_pass': None, 'menu_match': None,
                'reason_fields_complete': None, 'subjective_suitability': None}
    value = record.get('result', {})
    recs = value.get('recommendations', [])
    evaluation = case['evaluation']
    match = bool(recs) and all(r['menu_id'] in evaluation['acceptable_menu_ids'] for r in recs)
    complete = bool(recs) and all(set(evaluation['required_basis_fields']) <= set(r['basis_fields']) for r in recs)
    passed = (record['status'] == 'ok' and value.get('status') == 'recommend' and match and complete
              and factual.get('factual_violations') == [])
    return {'factual_check': factual, 'narrow_case_pass': passed, 'menu_match': match,
            'reason_fields_complete': complete, 'subjective_suitability': None}


def run(menus, evidence, cases, model, transport, mode, rates=None):
    rows = []
    for case in cases:
        start = perf_counter()
        try:
            baseline = {'status': 'ok', 'menu_ids': existing_recommend(case['text'], menus)}
        except (ValueError, KeyError, OSError):
            baseline = {'status': 'error', 'error_code': 'EXISTING_INPUT_OR_DATA_ERROR'}
        baseline['latency_ms'] = round((perf_counter()-start)*1000, 3)
        start = perf_counter()
        try:
            direct = v3.recommend(case['text'], menus, evidence, model, transport)
            # Keep input provenance once in the report, rather than duplicating all contexts.
            direct.pop('context', None)
            direct['status'] = 'ok'
        except DirectError as error:
            direct = {'status': 'error', 'error_code': str(error), 'usage': error.usage,
                      'rejected_response': error.candidate_response, 'origin': 'llm', 'api_calls': 1}
        direct['latency_ms'] = round((perf_counter()-start)*1000, 3)
        if mode == 'mock':
            direct.update(origin='mock_fixture', api_calls=0)
        direct['cost_usd_estimate'] = cost(direct['usage'], rates) if mode == 'live' else None
        direct['evaluation'] = check_easy(direct, case, menus, evidence, mode)
        rows.append({'case_id': case['id'], 'text': case['text'], 'existing': baseline, 'v3': direct})
    return {'version': v3.PROMPT_VERSION, 'mode': mode, 'model': model, 'repeat': 1,
            'created_at_utc': datetime.now(timezone.utc).isoformat(),
            'prompt_sha256': hashlib.sha256(v3.SYSTEM.encode('utf-8')).hexdigest(),
            'menu_snapshot_sha256': digest(menus),
            'rates_usd_per_million': rates, 'menus': menus, 'evidence_sha256': digest(evidence),
            'cases': cases, 'cases_sha256': digest(cases), 'runs': rows,
            'information_difference': 'Same text and catalogue. Baseline uses its original CSV/regex. V3 receives confirmed per-temperature description/ingredient/caffeine facts and guard hints; no numeric taste scores or sensory hypotheses. Evaluation annotations are not sent to the LLM.',
            'human_suitability': None, 'repeat_consistency': None}


def save(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    live = report['mode'] == 'live'
    menus = {m['menu_id']: m for m in report['menus']}
    lines = ['# LLM 직접 추천 v3 — 쉬운 발화 5개 실험 보고서', '',
             '## 실험 상태', '',
             ('실제 API 실행 결과입니다. 아래 평가는 제한된 개발 사례의 조건·메뉴·근거 확인이며 일반 추천 정확도가 아닙니다.'
              if live else '**무료 mock 검증본입니다. 실제 LLM 추천 결과는 아직 없고 추천 성능은 미측정입니다.**'), '',
             f"모델: {report['model']}. 발화별 1회, 자동 재시도 없음. 질문 이후 대화는 시험하지 않습니다.", '',
             '## 결과 요약', '', '| 발화 | 실제 응답/오류 | 메뉴 | 조건·메뉴·근거 점검 | 응답시간(ms) | 비용(USD) |',
             '|---|---|---|---|---:|---:|']
    for row in report['runs']:
        direct = row['v3']
        result = direct.get('result', {})
        names = ', '.join(menus[r['menu_id']]['name'] + ' ' + r['temperature'] for r in result.get('recommendations', [])) or '—'
        check = direct['evaluation']['narrow_case_pass']
        label = '미평가(mock)' if check is None else '충족' if check else '미충족/응답 검토 필요'
        latency = str(direct['latency_ms']) if live else '미측정'
        amount = direct['cost_usd_estimate']
        lines.append(f"| {row['text']} | {result.get('status', direct.get('error_code'))} | {names} | {label} | {latency} | {amount if amount is not None else '미상/미측정'} |")
    if live:
        passed = sum(r['v3']['evaluation']['narrow_case_pass'] is True for r in report['runs'])
        known = sum(r['v3']['cost_usd_estimate'] or 0 for r in report['runs'])
        unknown = sum(r['v3']['cost_usd_estimate'] is None for r in report['runs'])
        average = sum(r['v3']['latency_ms'] for r in report['runs']) / len(report['runs'])
        lines += ['', f'제한된 사전 기준 충족 {passed}/{len(report["runs"])}건. 평균 응답시간 {average:.1f}ms.',
                  f'알려진 usage의 비용 추정 소계 USD {known:.8f}, 비용 미상 {unknown}건. 실제 청구액과 다를 수 있습니다.']
    lines += ['', '## 발화별 상세 결과', '']
    for row, case in zip(report['runs'], report['cases']):
        direct = row['v3']
        lines += ['### ' + row['case_id'], '', '**발화:** ' + row['text'], '',
                  '**사전 검토 기준:** ' + case['evaluation']['rationale'], '',
                  '**허용 메뉴:** ' + ', '.join(case['evaluation']['acceptable_menu_ids']), '',
                  '**기존 방식:** `' + json.dumps(row['existing'], ensure_ascii=False) + '`', '',
                  '**v3의 추천·질문·자료 부족 또는 거부된 원래 응답:**', '', '```json',
                  json.dumps(direct.get('result') or direct.get('rejected_response') or {'error_code': direct.get('error_code')}, ensure_ascii=False, indent=2), '```', '',
                  '**점검 결과:** `' + json.dumps(direct['evaluation'], ensure_ascii=False) + '`', '',
                  '**토큰 usage:** `' + json.dumps(direct['usage'], ensure_ascii=False) + '`', '']
    lines += ['## 단점과 해석상 한계', '',
              '- 쉬운 발화 5개만 사용하므로 결과가 좋아도 실제 서비스의 정확도를 입증하지 못합니다.',
              '- 확인된 설명에서 고르기 쉬운 개발 사례입니다. 정답 메뉴 목록은 해당 자료에서 정했고 독립된 취향 평가가 아닙니다.',
              '- 단맛 잔류·떫음·알레르기·복잡한 부정·없는 메뉴·질문 후 대화는 이번 범위에서 제외했습니다.',
              '- 각 1회이므로 반복 일관성은 미측정입니다. 실제 사용자 만족도와 주관적 근거 적합성은 사람이 따로 검토해야 합니다.',
              '- 모델이 특정 메뉴명이나 미해결 조건을 누락하면 서버가 놓칠 수 있습니다. 한국어 조건 해석과 주입 방어에도 한계가 있습니다.',
              '- 저장된 v1 실제 DB 스냅샷과 조사 근거를 재사용합니다. 현재 판매 여부와 가격, 매장별 레시피를 보장하지 않습니다.',
              '- 기존 방식은 CSV/규칙, v3는 추가 설명과 성분 자료를 받습니다. 시스템 전체의 차이이며 모델만의 개선을 분리해 증명하지 않습니다.',
              '- 응답시간에는 HTTP와 검증을 포함하며 메뉴 로딩은 제외합니다. 기존 CSV 사전 생성과 Whisper 비용은 제외합니다.',
              '- 실패 응답과 서버 거부를 숨기지 않습니다. 서버 검증 통과와 추천 적합성은 다른 평가입니다.', '',
              '## 다음 판단', '',
              '실제 결과를 읽고 메뉴·온도·가격과 근거를 직접 확인한 뒤, 실패 사례를 보완하고 처음 쓰는 발화로 다시 평가합니다. 운영 웹·음성 기본값은 기존 방식입니다.']
    (directory/'report.ko.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v1-report', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, default=RESEARCHED_EVIDENCE)
    parser.add_argument('--mode', choices=['mock', 'live'], default='mock')
    parser.add_argument('--allow-paid-api', action='store_true')
    parser.add_argument('--model', default='not-configured')
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--rates', nargs=3, type=float)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'live' and (not args.allow_paid_api or not args.env_file or args.model == 'not-configured'):
        parser.error('Live requires --allow-paid-api --model --env-file; key owner runs personally.')
    if args.rates and any(not math.isfinite(r) or r < 0 for r in args.rates):
        parser.error('Rates must be finite and nonnegative.')
    if args.output_dir.exists():
        parser.error('Output folder already exists. Preserve previous results/attempts; use a new folder.')
    menus = json.loads(args.v1_report.read_text(encoding='utf-8'))['smoke']['catalog']
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    cases = json.loads(CASES_PATH.read_text(encoding='utf-8'))
    if len(cases) != 5 or len({c['id'] for c in cases}) != 5:
        parser.error('Exactly five unique easy cases required.')
    for case in cases:
        v3.prepare_context(case['text'], menus, evidence)
    previous = os.environ.get('OPENAI_API_KEY')
    try:
        if args.mode == 'live':
            from app.experiments.run_small_experiment import load_user_key
            os.environ['OPENAI_API_KEY'] = load_user_key(args.env_file)
            transport = recorded_transport(openai_transport, args.output_dir/'api-attempts.json', 5)
        else:
            transport = mock_transport
        report = run(menus, evidence, cases, args.model, transport, args.mode, args.rates)
        report['catalog_source'] = 'recorded_v1_snapshot'
        save(report, args.output_dir)
    finally:
        if previous is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = previous
    print('Saved results.json and report.ko.md. Share only results; never .env.')


if __name__ == '__main__':
    main()
