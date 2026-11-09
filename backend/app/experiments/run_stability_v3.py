"""Ten-call follow-up: 5 replays plus 5 paraphrases; no prompt changes or retries."""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path

from app.experiments.recorded_transport import recorded_transport
from app.experiments.run_easy_v3 import CASES_PATH, digest, mock_transport, run
from app.services import llm_direct_v3 as v3
from app.services.llm_direct import openai_transport
from app.services.sensory_tags import RESEARCHED_EVIDENCE

PARAPHRASES = {
    'easy_budget': '커피 종류는 제외하고, 차게 마실 수 있는 음료 중 3천 원을 넘지 않는 걸로 골라 주세요.',
    'easy_hot_coffee': '뜨거운 커피 한 잔 마시고 싶어요. 가격은 3천 원 이하로 부탁해요.',
    'easy_lemon_carbonation': '3,500원 이하로, 차갑고 탄산이 있으면서 레몬의 신맛을 느낄 수 있는 음료를 골라 주세요.',
    'easy_strawberry_milk': '우유와 딸기가 함께 들어간 음료를 아이스로 주세요. 4천 원 이하면 좋겠어요.',
    'easy_grape_carbonation': '시원한 청포도 풍미의 탄산음료가 좋아요. 3,500원 이하로 추천해 주세요.',
}


def prepare(reference, evidence, model):
    expected = json.loads(CASES_PATH.read_text(encoding='utf-8'))
    if reference.get('mode') != 'live' or reference.get('model') != model:
        raise ValueError('Reference must be a live result with the same model.')
    if reference.get('version') != v3.PROMPT_VERSION or reference.get('prompt_sha256') != hashlib.sha256(v3.SYSTEM.encode('utf-8')).hexdigest():
        raise ValueError('Prompt/version changed; do not interpret this as a stability-only experiment.')
    if reference.get('evidence_sha256') != digest(evidence):
        raise ValueError('Evidence changed; preserve the previous snapshot before comparing.')
    menus = copy.deepcopy(reference['menus'])
    if reference.get('menu_snapshot_sha256') != digest(menus) or reference.get('cases') != expected:
        raise ValueError('Reference catalogue or original case definitions do not match.')
    originals = {r['case_id']: r for r in reference['runs']}
    if set(originals) != set(PARAPHRASES) or len(reference['runs']) != 5:
        raise ValueError('Exactly five unique reference runs are required.')
    cases = []
    for group in ('replay', 'paraphrase'):
        for original in expected:
            if originals[original['id']]['text'] != original['text']:
                raise ValueError('Reference transcript differs from the original case.')
            case = copy.deepcopy(original)
            case.update(id=group+'_'+original['id'], parent_id=original['id'], group=group)
            if group == 'paraphrase':
                case['text'] = PARAPHRASES[original['id']]
            v3.prepare_context(case['text'], menus, evidence)
            cases.append(case)
    return menus, cases


def signature(record):
    if record.get('status') != 'ok' or record.get('origin') != 'llm':
        return None
    result = record['result']
    return {'status': result['status'],
            'selection': [(r['menu_id'], r['temperature']) for r in result['recommendations']]}


def compare(reference, report):
    originals = {r['case_id']: r['v3'] for r in reference['runs']}
    fresh = {c['parent_id']: row['v3'] for c, row in zip(report['cases'], report['runs']) if c['group'] == 'replay'}
    comparisons = []
    for case, row in zip(report['cases'], report['runs']):
        previous = originals[case['parent_id']] if case['group'] == 'replay' else fresh[case['parent_id']]
        a, b = signature(previous), signature(row['v3'])
        measured = report['mode'] == 'live' and a is not None and b is not None
        comparisons.append({'case_id': case['id'], 'parent_id': case['parent_id'], 'group': case['group'],
                            'compared_to': 'previous_session_original' if case['group'] == 'replay' else 'this_session_original',
                            'same_action_and_selection': a == b if measured else None,
                            'same_full_result': previous['result'] == row['v3']['result'] if measured else None,
                            'reference_selection': a, 'current_selection': b,
                            'narrow_case_pass': row['v3']['evaluation']['narrow_case_pass']})
    report.update(reference_sha256=digest(reference), comparisons=comparisons,
                  study='five cross-session replays plus five single paraphrases',
                  retries=0, max_api_calls=10,
                  limitations=['Different valid choices can both satisfy the request; consistency is separate from correctness.',
                               'Replays compare two sessions, one run in each. Paraphrases run once each.',
                               'Five easy development cases do not establish general accuracy or multi-turn capability.'])
    return report


def save(report, directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    live = report['mode'] == 'live'
    lines = ['# v3 반복·말투 변경 실험 보고서', '',
             '실제 API 결과입니다.' if live else '**무료 mock 검증입니다. 실제 추천 품질과 일관성은 미측정입니다.**', '',
             '## 실험 구성', '',
             '총 10회: 기존 발화 5개를 이번에 각 1회 다시 실행하고 직전 실행과 비교합니다. 말투 변경 5개는 각 1회 실행해 이번 원문 결과와 비교합니다.',
             '모델·프롬프트·메뉴·근거·사전 평가 기준을 유지했습니다. 별도 연결 호출·자동 재시도는 없습니다.', '',
             '## 결과 요약', '',
             '| 구분 | 제한된 메뉴·조건·근거 기준 충족 | 비교 가능한 응답 쌍 | 같은 행동·메뉴·온도 |', '|---|---:|---:|---:|']
    for group, label in [('replay', '동일 발화 재실행'), ('paraphrase', '말투 변경')]:
        values = [c for c in report['comparisons'] if c['group'] == group]
        count = sum(c['narrow_case_pass'] is True for c in values)
        comparable = sum(c['same_action_and_selection'] is not None for c in values)
        same = sum(c['same_action_and_selection'] is True for c in values)
        lines.append(f'| {label} | {str(count)+"/5" if live else "미측정"} | {comparable if live else "미측정"} | {same if live else "미측정"} |')
    known = [r['v3']['cost_usd_estimate'] for r in report['runs'] if r['v3']['cost_usd_estimate'] is not None]
    if live:
        average = sum(r['v3']['latency_ms'] for r in report['runs'])/len(report['runs'])
        lines += ['', f'평균 응답시간 {average/1000:.3f}초. 알려진 usage 비용 추정 소계 USD {sum(known):.8f}. 비용 미상 {len(report["runs"])-len(known)}건.']
    lines += ['', '## 발화별 실제 결과', '']
    for row, comparison in zip(report['runs'], report['comparisons']):
        direct = row['v3']
        lines += ['### ' + row['case_id'], '', row['text'], '',
                  '비교: `' + json.dumps(comparison, ensure_ascii=False) + '`', '',
                  '```json', json.dumps(direct, ensure_ascii=False, indent=2), '```', '',
                  '기존 방식: `' + json.dumps(row['existing'], ensure_ascii=False) + '`', '']
    lines += ['## 단점과 해석', '',
              '- 동일 발화는 두 시점에서 각 1회씩만 비교합니다. 같은 세션 내 여러 차례 반복이나 장기 안정성 검증이 아닙니다.',
              '- 말투 변경은 동일 조건을 유지하도록 사람이 작성한 개발용 문장 5개입니다. 각 1회이므로 해당 표현 자체의 반복 안정성도 알 수 없습니다.',
              '- 카페라떼와 에스프레소처럼 허용 후보가 여러 개이면 선택이 달라도 둘 다 올바를 수 있습니다. 같은 메뉴 여부를 정확도로 해석하지 않습니다.',
              '- 오류를 동일한 응답으로 세지 않습니다. 비교 가능한 쌍의 수와 조건 충족을 함께 봅니다.',
              '- 재질문·자료 부족·뒷맛·알레르기·복합 부정·질문 후 대화는 이번 범위에서 제외합니다.',
              '- 기존 방식과 v3는 제공 자료가 다릅니다. 사용자 만족도와 독립 관능 평가는 미측정입니다.',
              '- 저장 스냅샷 기준이며 현재 판매·가격·레시피를 보장하지 않습니다. 10개 실행으로 서비스 품질을 일반화하지 않습니다.',
              '- 토큰·비용은 JSON에 기록합니다. 입력 단가에 따른 추정으로 실제 청구액과 다를 수 있습니다.']
    (directory/'report.ko.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, default=RESEARCHED_EVIDENCE)
    parser.add_argument('--mode', choices=['mock', 'live'], default='mock')
    parser.add_argument('--model', required=True)
    parser.add_argument('--env-file', type=Path)
    parser.add_argument('--allow-paid-api', action='store_true')
    parser.add_argument('--rates', nargs=3, type=float)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'live' and (not args.allow_paid_api or not args.env_file):
        parser.error('Live requires --allow-paid-api --env-file; key owner runs personally.')
    if args.output_dir.exists():
        parser.error('Output already exists; preserve prior results and attempts.')
    if args.rates and any(not math.isfinite(r) or r < 0 for r in args.rates):
        parser.error('Rates must be finite nonnegative values.')
    reference = json.loads(args.reference.read_text(encoding='utf-8'))
    evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
    try:
        menus, cases = prepare(reference, evidence, args.model)
    except ValueError as error:
        parser.error(str(error))
    previous = os.environ.get('OPENAI_API_KEY')
    try:
        if args.mode == 'live':
            from app.experiments.run_small_experiment import load_user_key
            os.environ['OPENAI_API_KEY'] = load_user_key(args.env_file)
            transport = recorded_transport(openai_transport, args.output_dir/'api-attempts.json', 10)
        else:
            transport = mock_transport
        report = compare(reference, run(menus, evidence, cases, args.model, transport, args.mode, args.rates))
        save(report, args.output_dir)
    finally:
        if previous is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = previous
    print('Saved 10-case results.json and report.ko.md. Never share .env.')


if __name__ == '__main__':
    main()
