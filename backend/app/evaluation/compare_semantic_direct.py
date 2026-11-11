"""Free comparison of existing and semantic-direct wiring. No live mode or key loading."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from app.db.catalog import load_catalog
from app.services import llm_direct as previous
from app.services import llm_semantic_direct as semantic

DEFAULT_CASES = Path(__file__).with_name('semantic_direct_cases.json')


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def offline_guard(event, args):
    if event in ('socket.connect', 'socket.getaddrinfo'):
        raise RuntimeError('Network disabled for this free comparison')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        filename = os.path.basename(os.fsdecode(args[0]))
        if filename == '.env' or filename.startswith('.env.') or filename == 'backend.env':
            raise RuntimeError('Secret file reads disabled for this free comparison')


def catalogue_fixture():
    # Real metadata and options; SYNTHETIC availability, never the user's database.
    return [{'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
        'is_available': True, 'categories': list(m.categories),
        'available_temperatures': [t for t, _ in m.variants],
        'variants': [{'temperature': t, 'option_groups': m.option_groups} for t, _ in m.variants]} for m in load_catalog()]


def mocked_response(case, version):
    selected = {'menu_id': case['fixture_menu_id'], 'temperature': case['fixture_temperature'],
                'basis_fields': ['description']}
    value = {'status': 'recommend', 'recommendations': [selected],
             'questions': [], 'missing_information': [], 'unresolved_requirements': []}
    if version == 'previous': value['requested_menu_name'] = ''
    else:
        selected['option_ids'] = []
        value = {'request_summary': '사람이 작성한 예상 해석 fixture. 실제 모델 출력 아님.',
                 'constraints': case['expected_constraints'], 'decision': value}
    return {'status': 'completed', 'model': 'mock-not-a-real-model', 'usage': None,
        'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


def compare(output, mode='mock', model=semantic.DEFAULT_MODEL):
    dataset = json.loads(DEFAULT_CASES.read_text(encoding='utf-8'))
    menus = catalogue_fixture()
    evidence = json.loads(previous.DEFAULT_EVIDENCE.read_text(encoding='utf-8'))
    output = Path(output)
    requests = output / 'requests'
    requests.mkdir(parents=True, exist_ok=True)
    report = {'mode': mode, 'model_for_request_construction': model,
        'baseline': 'Existing selector files inherited unchanged from 769d2d9',
        'new_selector': semantic.PROMPT_VERSION,
        'catalogue_sha256': digest(menus), 'evidence_sha256': digest(evidence),
        'source_hashes': {name: hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
                          for name, module in [('previous', previous), ('semantic', semantic)]},
        'availability': 'synthetic all True', 'paid_api_calls': 0,
        'real_model_calls': 0, 'quality_measured': False, 'latency_measured': False,
        'consistency_measured': False, 'cases': []}
    for case in dataset['cases']:
        row = {'id': case['id'], 'text': case['text'],
               'handwritten_expected_constraints': case['expected_constraints']}
        for name, module in [('previous', previous), ('semantic', semantic)]:
            context = module.prepare_context(case['text'], menus, evidence)
            payload = module.build_request(context, model)
            if name == 'previous' and model.startswith('gpt-5.4-mini'):
                payload['reasoning'] = {'effort': 'none'}
            path = requests / (case['id'] + '.' + name + '.json')
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            record = {'request_sha256': digest(payload),
                      'request_utf8_bytes': len(json.dumps(payload, ensure_ascii=False).encode()),
                      'mock_transport_calls': 0, 'server_result': None, 'validation_error': None,
                      'usage': None, 'cost_usd': None, 'provider_seconds': None,
                      'request_file': 'requests/' + path.name}
            if name == 'previous':
                record.update(python_interpretation=context['guard'],
                    eligible_ids=[mid for mid, temperatures in context['allowed'].items() if temperatures])
            else:
                record.update(transcript_prefilter=False,
                    visible_available_ids=[menu['menu_id'] for menu in context['menus'] if menu['is_available']])
            if mode == 'mock':
                def send(request, record=record, case=case, name=name, payload=payload):
                    record['mock_transport_calls'] += 1
                    if record['mock_transport_calls'] != 1: raise RuntimeError('Unexpected retry')
                    if digest(request) != digest(payload): raise RuntimeError('Request changed')
                    return mocked_response(case, name)
                try:
                    record['server_result'] = module.recommend(case['text'], menus, evidence=evidence,
                                                               model=model, transport=send)['result']
                    record['fixture_validation'] = 'accepted'
                except previous.DirectError as error:
                    record['fixture_validation'] = 'rejected'
                    record['validation_error'] = str(error)
            else: record['fixture_validation'] = 'not_run'
            row[name] = record
        report['cases'].append(row)
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# 기존 방식과 LLM 의미 해석 방식: 무료 구조 검증', '',
        '이 보고서는 실제 LLM 추천 성능 비교가 아니다. 요청 구성과 사람이 작성한 고정 응답의 서버 검증을 비교했다.', '',
        '| 발화 | 기존 Python 선호/제외 | 기존 허용 후보 수 | 새 방식의 사전 의미 필터 | 기존 fixture 검증 | 새 fixture 검증 |',
        '|---|---|---|---|---|---|']
    for row in report['cases']:
        old, new = row['previous'], row['semantic']
        guard = old['python_interpretation']
        lines.append(f"| {row['text']} | {guard['flavors']} / {guard.get('excluded_flavors', [])} | {len(old['eligible_ids'])} | 없음 | {old['fixture_validation']} {old['validation_error'] or ''} | {new['fixture_validation']} |")
    lines += ['', '- 메뉴 45개·가격·온도·옵션·공식 설명은 양쪽 동일하다. 판매 상태는 시험용으로 전부 True다.',
        '- 기존은 정규식 조건 및 eligible_for_request/스키마 후보 제한을 제공한다. 새 방식은 원문과 전체 메뉴를 제공하고 같은 응답에서 해석·후보를 받는다.',
        '- 모델 ID는 같은 값으로 요청을 구성했다. 프롬프트/응답 스키마/서버 역할이 달라지는 파이프라인 실험이며 모델 자체를 비교하는 것이 아니다.',
        '- 각 requests/*.json과 results.json에서 실제 요청 및 모델이 받을 정보의 차이를 검토할 수 있다.',
        '- fixture는 정답 모델 출력이 아니라 사람이 작성한 예상 응답이다. accepted 수로 추천 정확도/속도/일관성/비용을 계산하면 안 된다.',
        '- 새 방식도 LLM이 원문의 조건을 누락하거나 잘못 정규화하면 서버가 의미상 오류를 놓칠 수 있다. 원문 인용 일치만으로 해석의 정확성을 입증하지 못한다.',
        '- 제외 맛의 설명 문자열 충돌 검사는 제한적·보수적이다. 부정된 메뉴 설명에서도 오탐할 수 있으며 성분 부재를 보장하지 않는다.',
        '- 실제 API/키 파일/DB/STT를 사용하지 않았다. 유료 실행 모드는 아직 제공하지 않는다. 기존 웹·음성 경로도 변경하지 않았다.', '']
    (output / 'report.ko.md').write_text('\n'.join(lines), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['request', 'mock'], default='mock')
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--model', default=semantic.DEFAULT_MODEL)
    args = parser.parse_args()
    sys.addaudithook(offline_guard)
    result = compare(args.output_dir, args.mode, args.model)
    print(f"Saved {len(result['cases'])} paired cases and eight request files. Paid API calls: 0.")
    print('Mock quality is unmeasured. Open: ' + str(args.output_dir / 'report.ko.md'))


if __name__ == '__main__': main()
