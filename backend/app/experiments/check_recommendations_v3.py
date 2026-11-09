"""Offline paired text inspection; no live mode and no credential loading."""
import argparse
import json
from pathlib import Path
from time import perf_counter

from app.services import llm_direct_v2 as v2, llm_direct_v3 as v3
from app.services.llm_direct import DirectError
from app.services.recommendation import recommend as existing_recommend
from app.services.sensory_tags import RESEARCHED_EVIDENCE

CASES = [
    {'id': 'budget_temperature', 'text': '삼천 원을 넘기지 않는 차가운 음료로 골라주세요.'},
    {'id': 'described_taste', 'text': '레몬의 산미와 탄산이 있는 차가운 음료를 추천해 주세요.'},
    {'id': 'unknown_finish', 'text': '단맛은 좋아요. 다 마신 뒤 단맛이 오래 남는 건 피하고 싶어요.'},
    {'id': 'unknown_milk', 'text': '우유는 안 돼요. 과일 맛 나는 음료가 좋겠어요.'},
    {'id': 'absent_menu', 'text': '바닐라 오트라떼로 추천해 주세요. 없으면 먼저 알려주세요.'},
]


def inspect(menus, evidence, cases, responses=None):
    rows = []
    for case in cases:
        context = v3.prepare_context(case['text'], menus, evidence)
        request = v3.build_request(context, 'offline-inspection')
        old_request = v2.build_request(context, 'offline-inspection')
        row = {'case_id': case['id'], 'text': case['text'], 'request': request,
               'input_characters_v2': len(old_request['input'][0]['content']),
               'input_characters_v3': len(request['input'][0]['content']),
               'llm_quality': None, 'human_review': {'suitability': None, 'reason_accuracy': None},
               'api_calls': 0, 'usage': None, 'cost_usd': None}
        start = perf_counter()
        try:
            row['existing'] = {'menu_ids': existing_recommend(case['text'], menus)}
        except (ValueError, KeyError, OSError):
            row['existing'] = {'error_code': 'EXISTING_INPUT_OR_DATA_ERROR'}
        row['existing_latency_ms'] = round((perf_counter()-start)*1000, 3)
        if responses is None:
            candidate = {'status': 'insufficient_data', 'requested_menu_name': '',
                         'recommendations': [], 'questions': [], 'unresolved_requirements': [],
                         'missing_information': ['MOCK 고정 응답: 실제 품질 미평가.']}
            row['origin'] = 'mock_fixture'
        else:
            if case['id'] not in responses:
                raise ValueError('Every case must have a response; partial fixtures are not silently filled.')
            candidate = responses[case['id']]
            row['origin'] = 'handwritten_response_validation'
        row['candidate_response'] = candidate
        try:
            row['validation'] = {'status': 'accepted', 'result': v3.validate_response(candidate, context)}
        except DirectError as error:
            row['validation'] = {'status': 'rejected', 'error_code': str(error)}
        rows.append(row)
    return {'version': v3.PROMPT_VERSION, 'mode': 'offline', 'runs': rows,
            'information_difference': 'Same text/catalogue. Existing uses original CSV/regex. V3 sees confirmed variant facts and limited guard hints, without editorial sensory hypotheses or numeric taste scores.',
            'limits': ['No API call, model latency, token measurement or recommendation quality measurement.',
                       'Character counts are not token counts. Cost is unknown, not measured zero.',
                       'No multi-turn memory, taste ground truth or complete Korean constraint parser.',
                       'Self-reported requested name/unresolved conditions may be omitted by an actual model.',
                       'V2 results are preserved; fixtures do not demonstrate model improvement.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--v1-report', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, default=RESEARCHED_EVIDENCE)
    parser.add_argument('--cases', type=Path)
    parser.add_argument('--responses', type=Path, help='Optional handwritten case-ID to response map; not live model results')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Output directory already exists; use a new directory to preserve results.')
    menus = json.loads(args.v1_report.read_text(encoding='utf-8'))['smoke']['catalog']
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    cases = json.loads(args.cases.read_text(encoding='utf-8')) if args.cases else CASES
    responses = json.loads(args.responses.read_text(encoding='utf-8')) if args.responses else None
    report = inspect(menus, evidence, cases, responses)
    args.output_dir.mkdir(parents=True)
    (args.output_dir/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# v3 무료 구조 검증', '', '실제 추천 품질·LLM 응답시간·토큰·비용은 미측정입니다.', '',
             '| 발화 | 응답 출처 | 검증 | v2 입력 문자 | v3 입력 문자 |', '|---|---|---|---:|---:|']
    for row in report['runs']:
        validation = row['validation']
        lines.append(f"| {row['text']} | {row['origin']} | {validation.get('error_code', validation['status'])} | {row['input_characters_v2']} | {row['input_characters_v3']} |")
    lines += ['', '문자 수 감소가 같은 비율의 토큰·시간·비용 감소를 보장하지 않습니다.',
              'JSON에는 기존 추천 결과와 새 요청 전문이 있어 두 방식의 정보 차이를 검토할 수 있습니다.',
              '고정 mock 응답은 추천기나 언어 이해 시뮬레이션이 아닙니다.']
    (args.output_dir/'results.ko.md').write_text('\n'.join(lines), encoding='utf-8')
    print('Offline report saved; no key access or paid call; model quality unmeasured.')


if __name__ == '__main__':
    main()
