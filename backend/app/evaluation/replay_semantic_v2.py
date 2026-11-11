"""Offline replay of recorded model outputs, NOT a new model quality evaluation."""
import argparse
import copy
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys

from app.evaluation.compare_semantic_direct import catalogue_fixture, digest, offline_guard
from app.services import llm_direct as previous
from app.services import llm_semantic_direct as semantic


def adapt_shape_only(value):
    """Move v1 decision fields into v2.decision. Do NOT change any semantic values."""
    return {'request_summary': copy.deepcopy(value['request_summary']),
            'constraints': copy.deepcopy(value['constraints']),
            'decision': {key:copy.deepcopy(item) for key,item in value.items()
                         if key not in ('request_summary','constraints')}}


def replay(output):
    fixture=json.loads(Path(__file__).with_name('semantic_v1_live_cases.json').read_text(encoding='utf-8'))
    snapshot=Path(__file__).with_name('semantic_v1_snapshot.py.txt')
    if digest(snapshot.read_text(encoding='utf-8'))!=fixture['semantic_source_hash']:
        raise ValueError('Snapshot does not match the actual paid-study source hash')
    name='app.evaluation._frozen_semantic_v1'
    loader=importlib.machinery.SourceFileLoader(name,str(snapshot))
    specification=importlib.util.spec_from_loader(name,loader)
    frozen=importlib.util.module_from_spec(specification)
    sys.modules[name]=frozen
    try: loader.exec_module(frozen)
    finally: sys.modules.pop(name,None)
    menus=catalogue_fixture()
    evidence=json.loads(previous.DEFAULT_EVIDENCE.read_text(encoding='utf-8'))
    if digest(menus)!=fixture['catalogue_sha256'] or digest(evidence)!=fixture['evidence_sha256']:
        raise ValueError('Replay data differs from the recorded study')
    report={'kind':'offline_recorded_response_replay','model_calls':0,'paid_api_calls':0,
            'new_model_quality_measured':False,'prompt_change_effect_measured':False,
            'source_results_sha256':fixture['source_results_sha256'],'cases':[]}
    for row in fixture['cases']:
        raw=row['raw_candidate']; unchanged=copy.deepcopy(raw)
        result={'task_id':row['task_id'],'text':row['text'],'raw_candidate':raw,
                'v1':None,'v2':None,'shape_adapter_only':True}
        for version,module,value in [('v1',frozen,copy.deepcopy(raw)),('v2',semantic,adapt_shape_only(raw))]:
            context=module.prepare_context(row['text'],menus,evidence)
            try:
                checked=module.validate_response(value,context)
                result[version]={'state':'accepted','error_code':None,
                    'delivered_ids':[item['menu_id'] for item in checked['recommendations']],
                    'normalizations':checked.get('normalizations',[]),
                    'raw_contract_issues':checked.get('raw_contract_issues',[])}
            except previous.DirectError as error:
                result[version]={'state':'rejected','error_code':str(error),'delivered_ids':[]}
        if raw!=unchanged: raise RuntimeError('Recorded raw response was mutated')
        if result['v1']['error_code']!=row['observed_validation_error']:
            raise RuntimeError('Historical validation was not reproduced')
        report['cases'].append(result)
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# 실제 v1 응답의 무료 재검증', '',
        'LLM을 다시 호출하지 않았다. 같은 기록 응답을 v1/v2 검증기에 넣은 사후 처리 비교다. v2는 바깥 응답 형식만 변환했고 해석·후보·미해결 내용은 바꾸지 않았다.', '',
        '| 발화 | v1 검증/전달 | v2 검증/전달 |', '|---|---|---|']
    for row in report['cases']:
        lines.append(f"| {row['text']} | {row['v1']['state']} {row['v1']['error_code'] or ''}; {len(row['v1']['delivered_ids'])}개 | {row['v2']['state']} {row['v2']['error_code'] or ''}; {len(row['v2']['delivered_ids'])}개 |")
    lines += ['', '- v1 코드 스냅샷·메뉴·설명은 실제 유료 실험 기록의 해시와 일치하는지 확인했다.',
        '- 중복 사례는 동일 메뉴/온도/옵션을 모두 사실 검증한 뒤 첫 등장 순서로 5개 전달하며 원응답 중복 위반은 별도 기록한다.',
        '- 미해결 조건을 함께 반환했던 이중 부정 응답은 여전히 거부한다. 내용을 삭제하거나 성공 응답으로 바꾸지 않았다.',
        '- v2 프롬프트가 실제 LLM의 해석/생성을 개선했는지는 아직 미측정이다. 다음 유료 검증에는 다른 말투의 별도 사례도 필요하다.',
        '- 이 결과로 새 모델 정확도가 2/4에서 3/4로 상승했다고 표현하면 안 된다. 기존 응답의 전달 가능성을 개선한 재생 시험이다.', '']
    (output/'report.ko.md').write_text('\n'.join(lines),encoding='utf-8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args()
    sys.addaudithook(offline_guard)
    report=replay(args.output_dir)
    print(f"Replayed {len(report['cases'])} recorded responses. Model/API calls: 0. New model quality unmeasured.")


if __name__=='__main__': main()
