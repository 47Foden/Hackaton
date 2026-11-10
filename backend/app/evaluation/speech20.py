"""Replay the twenty archive utterances. Offline diagnostics never call an API."""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import time
import zipfile
from pathlib import Path

from app.services.llm_direct import DEFAULT_EVIDENCE, DirectError, recommend
from app.services.recommendation_conditions import derive_conditions
from app.services.voice.transcription import TranscriptionError, transcribe_voice

MANIFEST = DEFAULT_EVIDENCE.parent / 'evaluation' / 'speech20.json'
BASELINE = MANIFEST.with_name('speech20-baseline-guards.json')


def load_manifest(path=MANIFEST):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    cases = data['cases']
    if data['schema_version'] != 1 or len(cases) != 20 or len({c['id'] for c in cases}) != 20:
        raise ValueError('Expected twenty distinct audio cases')
    if sum(c['split'] == 'prompt' for c in cases) != 12:
        raise ValueError('Expected twelve prompt examples and eight prompt holdouts')
    return data


def condition_mismatches(actual, expected):
    return {key: {'expected': value, 'actual': actual.get(key)}
            for key, value in expected.items() if actual.get(key) != value}


def verify_archive(path, manifest):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest['archive_sha256']:
        raise ValueError('Audio archive differs from the reviewed manifest')
    with zipfile.ZipFile(path) as archive:
        if set(archive.namelist()) != {c['audio_file'] for c in manifest['cases']}:
            raise ValueError('Unexpected archive entries')
        for case in manifest['cases']:
            if hashlib.sha256(archive.read(case['audio_file'])).hexdigest() != case['audio_sha256']:
                raise ValueError('Audio entry checksum mismatch')


def decode_mp3(audio):
    result = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'mp3', '-i', 'pipe:0', '-ac', '1',
                             '-ar', '16000', '-t', '31', '-f', 's16le', 'pipe:1'],
                            input=audio, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            timeout=15, check=True)
    if not result.stdout or len(result.stdout) > 30 * 16000 * 2:
        raise ValueError('Invalid or overlong evaluation audio')
    return result.stdout


def run(manifest, mode='offline', archive=None, menus=None, model=None, transcripts=None, transport=None):
    if mode not in ('offline', 'live-text', 'live-audio'):
        raise ValueError('Unknown evaluation mode')
    if mode != 'offline' and menus is None:
        raise ValueError('Live evaluation requires current DB menu availability and prices')
    if mode == 'live-audio': verify_archive(archive, manifest)
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    records = []
    for case in manifest['cases']:
        text = (transcripts or {}).get(case['audio_file'], case['reference_text'])
        row = {'case_id': case['id'], 'audio_file': case['audio_file'], 'split': case['split'],
               'reference_status': case['reference_status'], 'text': text,
               'origin': 'offline_guard_only', 'api_calls_attempted': 0}
        started = time.monotonic()
        try:
            if mode == 'live-audio':
                with zipfile.ZipFile(archive) as source:
                    text = transcribe_voice(decode_mp3(source.read(case['audio_file'])))
                row.update(text=text, origin='worker_transcription')
            actual = derive_conditions(text)
            row['conditions'] = actual
            row['condition_mismatches'] = condition_mismatches(actual, case['expected_conditions'])
            row['baseline_condition_mismatches'] = condition_mismatches(
                baseline['conditions'][case['id']], case['expected_conditions'])
            if mode != 'offline':
                row['api_calls_attempted'] = 1
                result = recommend(text, menus, model=model, transport=transport)
                row.update(origin='live_llm', result=result['result'], usage=result['usage'], model=result['model'])
            row['status'] = 'completed'
        except (DirectError, TranscriptionError) as error:
            row.update(status='failed', error_code=getattr(error, 'code', str(error)))
        row['elapsed_seconds'] = round(time.monotonic() - started, 3)
        records.append(row)
    report = {'mode': mode, 'reference_human_verified': manifest['human_verified'],
              'recommendation_quality': 'not_measured_no_human_menu_relevance_labels',
              'case_count': len(records), 'api_calls_attempted': sum(r['api_calls_attempted'] for r in records),
              'guard_case_matches': sum(r.get('condition_mismatches') == {} for r in records),
              'baseline_guard_case_matches': sum(r.get('baseline_condition_mismatches') == {} for r in records),
              'warning': manifest['evaluation_warning'], 'records': records}
    return report


def save_report(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    (output / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    with (output / 'results.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['case', 'split', 'transcript', 'status', 'guard_mismatches', 'recommended_ids', 'seconds'])
        for row in report['records']:
            writer.writerow([row['case_id'], row['split'], row['text'], row['status'],
                             json.dumps(row.get('condition_mismatches'), ensure_ascii=False),
                             ','.join(r['menu_id'] for r in row.get('result', {}).get('recommendations', [])),
                             row['elapsed_seconds']])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['offline', 'live-text', 'live-audio'], default='offline')
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', help='Exact Responses API model ID; default is the service configuration')
    args = parser.parse_args()
    manifest = load_manifest()
    if args.mode == 'live-audio' and args.archive is None:
        parser.error('--archive is required for live-audio')
    menus = None
    if args.mode != 'offline' and not os.environ.get('OPENAI_API_KEY'):
        parser.error('Live evaluation requires OPENAI_API_KEY in the backend environment')
    if args.mode != 'offline':
        from app.repositories.menus import list_menus
        menus = list_menus()
    report = run(manifest, args.mode, args.archive, menus, args.model)
    save_report(report, args.output)
    print(json.dumps({k: v for k, v in report.items() if k != 'records'}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
