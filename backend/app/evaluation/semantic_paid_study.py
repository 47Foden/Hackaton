"""User-terminal-only paid study; default mode is free plan, never loads .env.

Eight attempts maximum across resumes. A failed/unknown attempt is NOT retried.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.evaluation.compare_semantic_direct import DEFAULT_CASES, catalogue_fixture, digest, mocked_response
from app.services import llm_direct as previous
from app.services import llm_semantic_direct as semantic

RATES = {'input': .75, 'cached_input': .075, 'output': 4.5,
         'unit': 'USD per million tokens', 'checked_date': '2026-11-12',
         'source': 'https://developers.openai.com/api/docs/models/gpt-5.4-mini'}
INTERVAL = 30
STUDY_OUTPUT_TOKENS = 2048
SAFE_CODES = {'rate_limit_exceeded', 'slow_down', 'insufficient_quota', 'credit_balance_exhausted',
              'organization_spend_limit_exceeded', 'project_spend_limit_exceeded',
              'organization_usage_limit_exceeded', 'invalid_api_key', 'model_not_found',
              'invalid_json_schema', 'invalid_request_error', 'server_is_overloaded'}
SAFE_TYPES = {'rate_limit_error', 'insufficient_quota', 'invalid_request_error', 'server_error',
              'authentication_error', 'service_unavailable_error', 'tokens', 'requests'}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def token_cost(usage):
    if not isinstance(usage, dict): return None
    incoming, outgoing = usage.get('input_tokens'), usage.get('output_tokens')
    details = usage.get('input_tokens_details') or {}
    if not isinstance(details,dict): return None
    cached = details.get('cached_tokens', 0)
    if any(type(n) is not int or n < 0 for n in (incoming, outgoing, cached)) or cached > incoming: return None
    return ((incoming-cached)*.75 + cached*.075 + outgoing*4.5)/1_000_000


def safe_http_details(error):
    details = {'http_status': error.code, 'code': 'unclassified', 'type': 'unclassified', 'retry_after_seconds': None}
    try:
        body = json.loads(error.read(16384)).get('error', {})
        if isinstance(body, dict):
            if body.get('code') in SAFE_CODES: details['code'] = body['code']
            if body.get('type') in SAFE_TYPES: details['type'] = body['type']
    except (ValueError, OSError, AttributeError, TypeError): pass
    try:
        delay = float(error.headers.get('Retry-After', ''))
        if 0 <= delay <= 3600: details['retry_after_seconds'] = delay
    except (ValueError, TypeError, AttributeError): pass
    return details


def api_client(key):
    def send(payload):
        request = Request('https://api.openai.com/v1/responses',
            data=json.dumps(payload).encode('utf-8'),
            headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json'})
        try:
            with urlopen(request, timeout=90) as response: return json.load(response)
        except HTTPError as error:
            safe = previous.DirectError('PROVIDER_HTTP_'+str(error.code))
            safe.provider_details = safe_http_details(error)
            error.close()
            raise safe from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise previous.DirectError('PROVIDER_UNAVAILABLE') from None
    return send


def load_key(path):
    # Only called after interactive approval in the owner's CMD, never in plan/mock.
    from dotenv import dotenv_values
    try: value = dotenv_values(path, interpolate=False, encoding='utf-8-sig').get('OPENAI_API_KEY')
    except (OSError, UnicodeError): raise ValueError('Cannot read saved API key. No calls started.') from None
    if not isinstance(value, str) or not value.strip(): raise ValueError('Saved OPENAI_API_KEY is missing/empty. No calls started.')
    return value.strip()


def prepare_plan(cases_file=DEFAULT_CASES, previous_selector=previous):
    cases = json.loads(Path(cases_file).read_text(encoding='utf-8'))['cases']
    menus = catalogue_fixture()
    evidence = json.loads(previous.DEFAULT_EVIDENCE.read_text(encoding='utf-8'))
    tasks = []
    for index, case in enumerate(cases):
        for version in (('previous','semantic') if index % 2 == 0 else ('semantic','previous')):
            module = previous_selector if version == 'previous' else semantic
            context = module.prepare_context(case['text'], menus, evidence)
            payload = module.build_request(context, semantic.DEFAULT_MODEL)
            payload['reasoning'] = {'effort': 'none'}
            # Same experimental output cap on BOTH versions; production defaults stay unchanged.
            payload['max_output_tokens'] = STUDY_OUTPUT_TOKENS
            tasks.append({'id': case['id']+'.'+version, 'case': case, 'version': version,
                          'module': module, 'context': context, 'payload': payload})
    public = {'schema_version': 1, 'model': semantic.DEFAULT_MODEL, 'maximum_attempts': 8,
        'semantic_prompt_version': semantic.PROMPT_VERSION,
        'automatic_retries': 0, 'interval_seconds': INTERVAL,
        'study_max_output_tokens': STUDY_OUTPUT_TOKENS,
        'reference_estimate_usd': .025 * len(tasks),
        'reference_estimate_basis': 'Previous measured requests were about $0.025 each; not a measured semantic-run cost or billing cap.',
        'availability': 'synthetic all True', 'catalogue_sha256': digest(menus),
        'dataset_sha256': digest(cases),
        'baseline_provenance': getattr(previous_selector,'baseline_provenance',
                                      {'kind':'working-tree selector inherited from 769d2d9'}),
        'evidence_sha256': digest(evidence), 'pricing': RATES,
        'source_hashes': {name: digest(Path(module.__file__).read_text(encoding='utf-8'))
                          for name,module in [('previous',previous_selector),('semantic',semantic)]},
        'tasks': [{'id': task['id'], 'input': task['case']['text'],
                   'request_sha256': digest(task['payload']),
                   'request_utf8_bytes': len(json.dumps(task['payload'],ensure_ascii=False).encode()),
                   'max_output_tokens': task['payload']['max_output_tokens']} for task in tasks]}
    public['fingerprint'] = digest(public)
    public['planning_estimate_usd'] = sum(((row['request_utf8_bytes']+8192)*.75 + row['max_output_tokens']*4.5)/1_000_000
                                         for row in public['tasks'])
    return tasks, public


def assess(candidate, result, task):
    """Limited human-authored flavor annotation; not a general accuracy judge."""
    if not isinstance(candidate, dict): return None, None
    if task['version'] == 'semantic': candidate = semantic.response_view(candidate)
    selections = candidate.get('recommendations', [])
    if not isinstance(selections, list): return False, False
    expected = {(c['kind'], c['value']) for c in task['case']['expected_constraints']}
    if task['version'] == 'semantic':
        claims = candidate.get('constraints', [])
        actual = {(c.get('kind'), c.get('value')) for c in claims if isinstance(c, dict) and isinstance(c.get('kind'),str)
                  and isinstance(c.get('value'), (str,int,bool))} if isinstance(claims,list) else set()
    else:
        guard = task['context']['guard']
        actual = {('preferred_flavor',v) for v in guard['flavors']} | {('excluded_flavor',v) for v in guard.get('excluded_flavors',[])}
    by_id = {m['menu_id']:m for m in task['context']['menus']}
    valid = bool(result and selections and candidate.get('status') == 'recommend')
    for rec in selections:
        if not isinstance(rec,dict) or not isinstance(rec.get('menu_id'),str) or not isinstance(rec.get('temperature'),str) or rec['menu_id'] not in by_id:
            valid=False; continue
        menu = by_id[rec['menu_id']]
        if task['version'] == 'semantic': facts = task['context']['facts'].get((rec['menu_id'],rec.get('temperature')), {})
        else:
            facts = {f['field']:f['value'] for f in task['context']['facts'].values()
                     if f['menu_id']==rec['menu_id'] and f['temperature']==rec.get('temperature')}
        description = facts.get('description','')
        valid &= menu['is_available'] and bool(description)
        for kind,value in expected:
            if kind=='preferred_flavor': valid &= value in description
            if kind=='excluded_flavor': valid &= value not in description
    return bool(valid), actual == expected


def save(study, output, secret=''):
    study['attempts_started'] = len(study['attempts'])
    study['paid_api_attempts'] = len(study['attempts']) if study['mode']=='live' else 0
    study['known_cost_usd'] = round(sum(row.get('cost_usd') or 0 for row in study['attempts']), 6)
    study['cost_complete'] = study['mode']=='live' and bool(study['attempts']) and all(row.get('usage') is not None for row in study['attempts'])
    encoded = json.dumps(study, ensure_ascii=False, indent=2)+'\n'
    if secret: encoded = encoded.replace(secret,'[REDACTED]')
    temporary = output/'results.tmp'
    temporary.write_text(encoded, encoding='utf-8')
    temporary.replace(output/'results.json')
    # Build the report from the already-redacted object too.
    clean = json.loads(encoded)
    lines = ['# 기존/새 의미 해석 방식 비교', '', f"실행 모드: {clean['mode']}. 모델: {clean['plan']['model']}.", '',
        '| 발화 | 방식 | 상태 | 모델 후보 | 제한된 후보 조건 검사 | 해석 기준 일치 | API 초 | 비용 USD |',
        '|---|---|---|---|---|---|---|---|']
    baseline_commit=clean['plan'].get('baseline_provenance',{}).get('main_commit')
    if baseline_commit:
        lines.insert(3,f"기존 기준: 고정 main {baseline_commit}. 신규: {clean['plan'].get('semantic_prompt_version')}.")
    for row in clean['attempts']:
        candidate = semantic.response_view(row.get('model_candidate'))
        selected = candidate.get('recommendations',[]) if isinstance(candidate,dict) else []
        ids = [r.get('menu_id') for r in selected if isinstance(r,dict)] if isinstance(selected,list) else []
        status = row['state'] + (' (normalized)' if row.get('raw_contract_issues') else '')
        lines.append(f"| {row['input']} | {row['version']} | {status} {row.get('error_code') or ''} | {ids} | {row.get('candidate_annotation_check')} | {row.get('interpretation_annotation_check')} | {row.get('provider_seconds')} | {row.get('cost_usd')} |")
    lines += ['', f"시도 {clean['attempts_started']}/8. 확인 비용 ${clean['known_cost_usd']:.6f}. 비용 기록 완전 여부 {clean['cost_complete']}.", '',
        '- 후보 검사는 사람이 작성한 딸기/레몬/망고 조건 및 서버 검증 통과 여부에 한정한다. 4개 발화 각 1회로 전체 정확도·속도·일관성 향상을 단정하지 않는다.',
        '- 해석 기준 일치는 기존 방식에서는 Python 조건, 새 방식에서는 LLM이 반환한 조건을 비교한다. 기존 LLM의 내부 해석을 관찰한 값이 아니다.',
        '- 모델·원문·메뉴 자료는 동일하지만 프롬프트·해석 힌트·허용 후보·응답 스키마가 다르다. 모델 학습/모델 자체 비교가 아닌 파이프라인 비교다.',
        '- 판매 여부는 모두 True인 시험 자료다. 실제 DB·STT·서비스 배포 성능을 평가하지 않았다. 설명상 맛 단서는 성분 미포함/알레르기 안전 보장이 아니다.',
        '- 공급자 오류/중단 항목은 미평가(null)다. 완료·실패·과금 불명 항목을 자동 재시도하지 않는다. 같은 파일을 재실행하면 아직 시작하지 않은 항목만 실행한다.',
        '- 호출 간 30초 간격은 실험용 속도 조절이며 API 응답시간에 포함하지 않는다. 429 방지를 보장하지 않는다. 공급자 오류가 나면 중단한다.',
        '- mock의 후보/해석/시간/토큰/비용 평가는 모두 미측정이다. 근거의 의미상 정확성과 주관적 적합성은 사람이 원본 응답·검증 결과를 검토해야 한다.',
        '- normalized 표시는 원응답의 중복 메뉴를 검증 후 제거했다는 뜻이다. 원응답 계약 위반은 raw_contract_issues/raw_contract_valid로 별도 기록하며 모델 생성 품질 향상으로 계산하지 않는다.',
        '- 키 및 전체 오류 본문은 기록하지 않는다. 사용량이 없으면 총 청구액을 확정할 수 없다. 보수적 계획액도 강제 결제 상한은 아니다.', '']
    (output/'report.ko.md').write_text('\n'.join(lines),encoding='utf-8')


def run_study(tasks, plan, output, client, *, mode='live', wait=time.sleep, secret=''):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    result_file=output/'results.json'
    study=json.loads(result_file.read_text(encoding='utf-8')) if result_file.exists() else {
        'mode':mode,'created_at_utc':utc_now(),'plan':plan,'attempts':[],
        'statistical_accuracy_measured':False,'consistency_measured':False}
    if study['plan']['fingerprint']!=plan['fingerprint'] or study['mode']!=mode:
        raise ValueError('Study input/code changed; refusing to mix results.')
    for row in study['attempts']:
        if row['state']=='started': row['state']='unknown_after_interruption'
    tried={row['task_id'] for row in study['attempts']}
    if len(study['attempts'])>8 or len(tried)!=len(study['attempts']): raise ValueError('Invalid study ledger')
    for task in tasks:
        if task['id'] in tried: continue
        if len(study['attempts'])>=8: break
        if study['attempts'] and mode=='live':
            last=study['attempts'][-1]
            elapsed=time.time()-datetime.fromisoformat(last['started_at_utc']).timestamp()
            delay=max(INTERVAL,last.get('provider_details',{}).get('retry_after_seconds') or 0)-elapsed
            if delay>0:
                print(f'Waiting {delay:.0f}s before the next request.',flush=True); wait(delay)
        row={'task_id':task['id'],'input':task['case']['text'],'version':task['version'],
             'state':'started','started_at_utc':utc_now(),'model_candidate':None,'server_result':None,
             'usage':None,'cost_usd':None,'candidate_annotation_check':None,'interpretation_annotation_check':None,
             'raw_contract_valid':None,'raw_contract_issues':[]}
        study['attempts'].append(row)
        save(study,output,secret)  # Write BEFORE the paid attempt; a crash is never silently retried.
        print(f"{'API' if mode=='live' else 'Mock'} call {len(study['attempts'])}/8 started: {task['id']}",flush=True)
        started=time.perf_counter()
        try:
            envelope=client(task)
            row['provider_seconds']=round(time.perf_counter()-started,3) if mode=='live' else None
            row['model_returned']=envelope.get('model')
            usage=envelope.get('usage')
            row['usage']={k:usage[k] for k in ('input_tokens','output_tokens','total_tokens','input_tokens_details','output_tokens_details') if k in usage} if isinstance(usage,dict) and mode=='live' else None
            row['cost_usd']=token_cost(row['usage'])
            row['state']='response_received'
            try:
                candidate=json.loads(previous.response_text(envelope)); row['model_candidate']=candidate
                row['server_result']=task['module'].validate_response(candidate,task['context'])
                row['state']='accepted'
                row['raw_contract_issues']=row['server_result'].get('raw_contract_issues',[])
                row['raw_contract_valid']=not row['raw_contract_issues']
            except (ValueError,KeyError,TypeError,AttributeError) as error:
                row['state']='validation_rejected'
                row['raw_contract_valid']=False
                row['error_code']=str(error) if isinstance(error,(previous.DirectError,task['module'].DirectError)) else 'INVALID_RESPONSE'
            if mode=='live':
                row['candidate_annotation_check'],row['interpretation_annotation_check']=assess(row['model_candidate'],row['server_result'],task)
        except previous.DirectError as error:
            row.update(state='provider_error_unmeasured',error_code=str(error),
                       provider_details=getattr(error,'provider_details',{}))
            row['provider_seconds']=round(time.perf_counter()-started,3) if mode=='live' else None
        except KeyboardInterrupt:
            row['state']='unknown_after_interruption'
        except (ValueError,TypeError,AttributeError):
            row.update(state='provider_error_unmeasured',error_code='INVALID_PROVIDER_ENVELOPE')
        finally: save(study,output,secret)
        if row['state'] in ('provider_error_unmeasured','unknown_after_interruption'):
            print('Stopped without retry. Existing attempts are preserved.',flush=True); break
    save(study,output,secret)
    return study


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=['plan','mock','live'],default='plan')
    parser.add_argument('--output-dir',type=Path,required=True)
    parser.add_argument('--env-file',type=Path)
    parser.add_argument('--allow-paid-api',action='store_true')
    parser.add_argument('--cases-file',type=Path,default=DEFAULT_CASES)
    parser.add_argument('--baseline-main',action='store_true',help='Use verified pinned main, not working-tree improved selector')
    args=parser.parse_args()
    baseline=previous
    if args.baseline_main:
        from app.evaluation.main_selector_baseline import load_main_selector
        baseline=load_main_selector()
    tasks,plan=prepare_plan(args.cases_file,baseline)
    if args.baseline_main: print('Baseline: pinned origin/main '+plan['baseline_provenance']['main_commit'][:7])
    print(f"Same model: {plan['model']}. At most 8 attempts across resumes; no automatic retries.")
    print(f"Prior-run reference estimate for eight calls: about ${plan['reference_estimate_usd']:.2f}; actual semantic-run cost is not measured yet.")
    print(f"Equal output cap: {STUDY_OUTPUT_TOKENS} tokens per call. Conservative byte-based allowance: ${plan['planning_estimate_usd']:.3f}; NOT expected charges or a guaranteed billing cap.")
    if args.mode=='plan':
        args.output_dir.mkdir(parents=True,exist_ok=True)
        (args.output_dir/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print('Free preflight passed. No key file read; no API calls.'); return
    if args.mode=='mock':
        from app.evaluation.compare_semantic_direct import offline_guard
        sys.addaudithook(offline_guard)
        run_study(tasks,plan,args.output_dir,
            lambda task:mocked_response(task['case'],task['version']),mode='mock')
        print('Mock study saved. Quality is unmeasured. Paid calls: 0.'); return
    if not args.allow_paid_api or not sys.stdin.isatty() or args.env_file is None:
        print('Live mode requires explicit paid flag, key-owner terminal and --env-file. No calls.'); return
    args.output_dir.mkdir(parents=True,exist_ok=True)
    lock=args.output_dir/'study.lock'
    try: descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        print('Study is already running or a prior lock remains. Do not run another paid copy.'); return
    os.close(descriptor)
    secret=''
    try:
        existing=args.output_dir/'results.json'
        if existing.exists():
            saved=json.loads(existing.read_text(encoding='utf-8'))
            if saved['plan']['fingerprint']!=plan['fingerprint'] or saved['mode']!='live':
                print('Inputs/code changed. Existing results preserved; no calls.'); return
            remaining=8-len(saved['attempts'])
            if remaining<=0: print('All eight attempt slots used. No new API calls.'); return
            print(f'{remaining} unstarted calls remain. Failed/unknown calls will NOT be repeated.')
        print('PAID API. Key will be read locally from saved .env, never printed or saved in results.')
        if input('Type RUN8 to approve remaining calls within this eight-attempt study: ').strip()!='RUN8':
            print('Cancelled. No API calls.'); return
        secret=load_key(args.env_file)
        transport=api_client(secret)
        run_study(tasks,plan,args.output_dir,lambda task:transport(task['payload']),secret=secret)
        print('Saved results.json and report.ko.md in: '+str(args.output_dir.resolve()))
    except (ValueError,OSError):
        print('Study/key setup failed. Existing results preserved; no automatic retries.')
    finally:
        secret=''
        lock.unlink(missing_ok=True)


if __name__=='__main__': main()
