"""User-run bounded experiment. Mock default never opens any credential file."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlparse
from urllib.request import urlopen

from app.db.catalog import load_catalog
from app.experiments.compare_recommendations import CASES, compare, mock_transport
from app.experiments.menu_evidence import DEFAULT_EVIDENCE, prepare, validate_evidence
from app.services.llm_direct import DirectError, catalog_snapshot, openai_transport

MODEL = 'gpt-5.4-mini-2026-03-17'
SMOKE = [{'id': 'connection_check', 'text': '3000원 이하 차가운 음료 추천해 주세요.',
          'constraints': {'max_price_krw': 3000, 'temperature': 'COLD'}}]


def load_user_key(path):
    """Called only by the user in live mode. Import only the key, not other .env settings."""
    from dotenv import dotenv_values
    values = dotenv_values(path, encoding='utf-8-sig', interpolate=False)
    key = values.get('OPENAI_API_KEY')
    if not isinstance(key, str) or not key.strip():
        raise DirectError('MISSING_API_KEY')
    return key.strip()


def bounded_transport(transport, max_calls=6):
    calls = 0

    def send(payload):
        nonlocal calls
        if calls >= max_calls:
            raise DirectError('CALL_LIMIT_REACHED')
        calls += 1
        request = dict(payload)
        # Explicitly choose non-reasoning mode for this fixed, documented model.
        request['reasoning'] = {'effort': 'none'}
        return transport(request)

    return send


def run(menus, transport, mode, rates):
    report = {'mode': mode, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
              'model': MODEL, 'max_calls': 6, 'retries': 0, 'comparison': None,
              'limitations': ['One trial per utterance cannot measure repeat consistency.',
                             'Quality requires human review; mock cannot establish quality.',
                             'Menu snapshot was loaded once; prices/availability may change.',
                             'Ingredient/caffeine exclusions without machine-verifiable metadata fail closed.']}
    send = bounded_transport(transport)
    report['smoke'] = compare(menus, SMOKE, 1, MODEL, send, mode, rates)
    if report['smoke']['runs'][0]['methods']['llm_direct']['status'] != 'ok':
        report['stopped_after_smoke_error'] = True
        return report
    print('Connection response validated. Running five utterances (one call each).', flush=True)
    report['comparison'] = compare(menus, CASES, 1, MODEL, send, mode, rates)
    return report


def validate_resume(previous, mode, rates):
    """Check resumability before opening credentials or calling a transport."""
    if (not isinstance(previous, dict) or previous.get('model') != MODEL
            or previous.get('mode') != mode or previous.get('comparison') is not None):
        raise DirectError('INVALID_RESUME_REPORT')
    smoke = previous.get('smoke', {})
    runs = smoke.get('runs', [])
    if len(runs) != 1 or smoke.get('cost_rates_usd_per_million') != rates:
        raise DirectError('INVALID_RESUME_REPORT')
    record = runs[0]['methods']['llm_direct']
    # These errors establish a parsed model response, rather than failed authentication/network.
    semantic_errors = {'CONSTRAINT_VIOLATION', 'UNVERIFIED_EXCLUSION', 'INVALID_MENU_ID', 'UNAVAILABLE_OPTION'}
    if record.get('status') != 'ok' and not (record.get('error_code') in semantic_errors
                                             and isinstance(record.get('rejected_response'), dict)):
        raise DirectError('RESUME_REQUIRES_RECEIVED_RESPONSE')
    return catalog_snapshot(smoke['catalog'])


def resume_run(previous, transport, mode, rates):
    """Reuse an already received smoke response; do not spend another smoke call."""
    menus = validate_resume(previous, mode, rates)
    report = json.loads(json.dumps(previous))
    report['resumed_at_utc'] = datetime.now(timezone.utc).isoformat()
    report['resume_note'] = 'Reused original smoke snapshot and response; five new calls, no repeated smoke.'
    report['stopped_after_smoke_error'] = False
    report['comparison'] = compare(menus, CASES, 1, MODEL, bounded_transport(transport, 5), mode, rates)
    return report


def save_report(report, output):
    output.mkdir(parents=True, exist_ok=True)
    (output/'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    phases = [report['smoke']] + ([report['comparison']] if report['comparison'] else [])
    names = {m['menu_id']: m['name'] for m in report['smoke']['catalog']}
    lines = ['# 첫 LLM 직접 추천 실험', '', f"실행 방식: {report['mode']} / 모델: {report['model']}", '',
             '연결 확인 1회 후 다섯 발화 각 1회. 자동 재시도 없음. 키는 보고서에 기록하지 않음.',
             '반복 일관성은 미측정이며 실제 적합성/근거 정확성은 사람 검토가 필요함.', '']
    total = 0
    unknown_cost = False
    for phase in phases:
        for row in phase['runs']:
            lines += ['## ' + row['case_id'], '', row['text'], '']
            for name, record in row['methods'].items():
                label = '기존 추천' if name == 'existing' else 'LLM 직접 추천'
                lines.append(f"**{label}**: {record['status']} / {record['latency_ms']} ms")
                if record['status'] == 'error':
                    lines += ['', '검증/실행 오류: ' + record['error_code']]
                result = record.get('result') or record.get('rejected_response')
                if isinstance(result, dict):
                    lines += ['', '```json', json.dumps(result, ensure_ascii=False, indent=2), '```']
                    ids = result.get('menu_ids', [r.get('menu_id') for r in result.get('recommendations', []) if isinstance(r, dict)])
                    lines += ['', '메뉴 이름: ' + (', '.join(names.get(mid, str(mid)) for mid in ids) or '후보 없음')]
                if name == 'llm_direct':
                    cost = record['cost_usd_estimate']
                    if cost is None:
                        unknown_cost = True
                    else:
                        total += cost
                    lines += ['', 'usage: ' + json.dumps(record['usage'], ensure_ascii=False),
                              '비용 추정(USD): ' + str(cost)]
                lines.append('')
    lines += ['## 비용 및 한계', '', f'usage가 있는 호출의 합계 추정: USD {total:.6f}.',
              'usage 없는 호출 비용은 미상이다.' if unknown_cost else '모든 기록에 비용 추정이 있다.',
              '계정 청구서/잔액과 다를 수 있으며 사용한 단가는 JSON에 기록한다.',
              '기존 방식의 Pretuning 사전 생성 비용과 Whisper 비용은 제외한다.']
    (output/'results.ko.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('mock', 'live'), default='mock')
    parser.add_argument('--allow-paid-api', action='store_true')
    parser.add_argument('--env-file', type=Path, help='Only the user should run live with their private file')
    parser.add_argument('--menus-url', default='http://localhost:8000/api/menus')
    parser.add_argument('--menus', type=Path, help='Explicit saved API snapshot, no synthetic availability implied')
    parser.add_argument('--resume-report', type=Path, help='Received smoke report; reuse its snapshot and make only five new calls')
    parser.add_argument('--rates', type=float, nargs=3, required=True, help='USD per million: input cached-input output')
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    import math
    if any(not math.isfinite(rate) or rate < 0 for rate in args.rates):
        parser.error('Rates must be finite and nonnegative')
    if args.mode == 'live' and (not args.allow_paid_api or not args.env_file):
        parser.error('Live requires --allow-paid-api and --env-file; run personally, never paste the key')
    if args.output_dir.exists() and (args.output_dir/'results.json').exists():
        parser.error('Output already exists. Inspect the previous result; choose a new folder for a new paid run.')
    try:
        previous_report = None
        if args.resume_report:
            if args.menus:
                parser.error('--resume-report reuses its original snapshot; do not also pass --menus')
            previous_report = json.loads(args.resume_report.read_text(encoding='utf-8-sig'))
            raw = validate_resume(previous_report, args.mode, args.rates)
        elif args.menus:
            raw = json.loads(args.menus.read_text(encoding='utf-8-sig'))
        else:
            parsed = urlparse(args.menus_url)
            if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1') or parsed.username or parsed.password:
                parser.error('Only the local menu API is allowed; use --menus for an explicit file')
            with urlopen(args.menus_url, timeout=10) as response:
                raw = json.load(response)
        menus = raw['menus'] if isinstance(raw, dict) else raw
        if previous_report is None:
            evidence = validate_evidence(json.loads(DEFAULT_EVIDENCE.read_text(encoding='utf-8')), load_catalog())
            if {m['menu_id'] for m in menus} != {m.menu_id for m in load_catalog()}:
                raise DirectError('CATALOG_ID_MISMATCH')
            enriched, _ = prepare(evidence, menus, CASES, MODEL)
    except (OSError, URLError, ValueError, KeyError, TypeError):
        parser.exit(2, 'Menu/evidence preparation failed. No paid API call was made.\n')
    previous = os.environ.get('OPENAI_API_KEY')
    try:
        if args.mode == 'live':
            os.environ['OPENAI_API_KEY'] = load_user_key(args.env_file)
        transport = openai_transport if args.mode == 'live' else mock_transport
        report = resume_run(previous_report, transport, args.mode, args.rates) if previous_report is not None else run(
            enriched, transport, args.mode, args.rates)
        if previous_report is None:
            report['catalog_source'] = 'explicit_file' if args.menus else 'local_api'
        save_report(report, args.output_dir)
    except (DirectError, ImportError, OSError):
        parser.exit(2, 'Credential/dependency/output error. No credential value is printed.\n')
    finally:
        if previous is None:
            os.environ.pop('OPENAI_API_KEY', None)
        else:
            os.environ['OPENAI_API_KEY'] = previous
    print('Saved results.json and results.ko.md. Share only these result files, never .env.')
    if report['comparison'] is None:
        parser.exit(3, 'Stopped after smoke response error. See the saved report; five-case comparison was NOT run.\n')


if __name__ == '__main__':
    main()
