"""Versioned editorial hypotheses, separate from verified menu facts and scores."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TABLE = ROOT/'common/experiments/llm_direct/sensory_annotations_v2.json'
RESEARCHED_TABLE = ROOT/'common/experiments/llm_direct/sensory_annotations_researched_v2.json'
RESEARCHED_EVIDENCE = ROOT/'common/experiments/llm_direct/menu_evidence_researched_v2.json'


def evidence_digest(evidence):
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def load_annotations(evidence, path=None):
    expected_digest = evidence_digest(evidence)
    table = None
    # Explicit paths never fall back silently. Default lookup supports both preserved snapshots.
    for candidate in ([path] if path is not None else [DEFAULT_TABLE, RESEARCHED_TABLE]):
        if not candidate.is_file():
            continue
        value = json.loads(candidate.read_text(encoding='utf-8'))
        if value.get('evidence_sha256') == expected_digest:
            table = value
            break
    if table is None or table.get('is_gold_standard') is not False:
        raise ValueError('Sensory annotations must match evidence and must not claim ground truth')
    definitions = table['definitions']
    expected = {(m['menu_id'], temp): fields for m in evidence['menus'] for temp, fields in m['variants'].items()}
    seen = set()
    for row in table['profiles']:
        key = row['menu_id'], row['temperature']
        if key not in expected or key in seen or set(row['tags']) != set(definitions):
            raise ValueError('Sensory profile ID/temperature/tag set mismatch')
        seen.add(key)
        for tag, record in row['tags'].items():
            if set(record) != {'state', 'basis_fields', 'rationale'} or record['state'] not in ('supported', 'inferred', 'unknown'):
                raise ValueError('Invalid sensory annotation')
            if not isinstance(record['rationale'], str) or not record['rationale'].strip():
                raise ValueError('Annotation rationale required')
            fields = record['basis_fields']
            if not isinstance(fields, list) or any(not isinstance(f, str) or f not in expected[key] for f in fields):
                raise ValueError('Invalid annotation basis')
            if record['state'] == 'unknown':
                if fields:
                    raise ValueError('Unknown tags cannot pretend to have evidence')
            elif not fields or any(expected[key][f]['status'] != 'verified' for f in fields):
                raise ValueError('Annotation requires verified basis fields')
            if definitions[tag]['kind'] == 'subjective' and record['state'] == 'supported':
                raise ValueError('Subjective texture/finish cannot be promoted to verified fact')
    if seen != set(expected):
        raise ValueError('Incomplete sensory table')
    return table


def context_annotations(evidence, visible_menu_options):
    table = load_annotations(evidence)
    index = {(row['menu_id'], row['temperature']): row for row in table['profiles']}
    annotations = {}
    for menu in visible_menu_options:
        for variant in menu['variants']:
            mid, temp = menu['menu_id'], variant['temperature']
            for tag, record in index[mid, temp]['tags'].items():
                aid = f'tag:{mid}:{temp}:{tag}'
                annotations[aid] = {'menu_id': mid, 'temperature': temp, 'tag': tag, **record,
                                    'basis_fact_ids': [f'{mid}:{temp}:{f}' for f in record['basis_fields']]}
    return {'version': table['version'], 'is_gold_standard': False,
            'annotation_sha256': evidence_digest(table),
            'definitions': table['definitions'], 'interpretation_guide': table['interpretation_guide'],
            'annotations': annotations}
