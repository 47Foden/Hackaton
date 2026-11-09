import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest

from app.experiments.run_easy_v3 import CASES_PATH, ROOT, digest, mock_transport, run
from app.experiments.run_stability_v3 import compare, prepare, signature
from app.services import llm_direct_v3 as v3
from app.services.sensory_tags import RESEARCHED_EVIDENCE


class StabilityV3Tests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(RESEARCHED_EVIDENCE.read_text(encoding='utf-8'))
        menus = json.loads((ROOT/'docs/experiments/2026-11-09-first-live/results.json').read_text(encoding='utf-8'))['smoke']['catalog']
        cases = json.loads(CASES_PATH.read_text(encoding='utf-8'))
        self.reference = {'mode': 'live', 'model': 'fixture', 'version': v3.PROMPT_VERSION,
                          'prompt_sha256': hashlib.sha256(v3.SYSTEM.encode('utf-8')).hexdigest(),
                          'evidence_sha256': digest(self.evidence), 'menus': menus,
                          'menu_snapshot_sha256': digest(menus), 'cases': cases,
                          'runs': [{'case_id': c['id'], 'text': c['text'], 'v3': {
                              'status': 'ok', 'origin': 'llm', 'result': {'status': 'recommend',
                              'recommendations': [{'menu_id': c['evaluation']['acceptable_menu_ids'][0],
                                                    'temperature': c['evaluation']['hard_constraints']['temperature']}]}}} for c in cases]}

    def test_exactly_ten_distinct_cases_and_same_evaluation(self):
        _, cases = prepare(self.reference, self.evidence, 'fixture')
        self.assertEqual(len(cases), 10)
        self.assertEqual(len({c['id'] for c in cases}), 10)
        for a, b, original in zip(cases[:5], cases[5:], self.reference['cases']):
            self.assertEqual(a['text'], original['text'])
            self.assertNotEqual(a['text'], b['text'])
            self.assertEqual(a['evaluation'], b['evaluation'])
            self.assertEqual(a['parent_id'], b['parent_id'])

    def test_changed_prompt_model_or_evidence_blocks_comparison(self):
        for key in ('prompt_sha256', 'model', 'evidence_sha256', 'menu_snapshot_sha256'):
            reference = copy.deepcopy(self.reference)
            reference[key] = 'changed'
            with self.subTest(key=key), self.assertRaises(ValueError):
                prepare(reference, self.evidence, 'fixture')

    def test_mock_consistency_and_quality_not_scored(self):
        menus, cases = prepare(self.reference, self.evidence, 'fixture')
        report = compare(self.reference, run(menus, self.evidence, cases, 'fixture', mock_transport, 'mock'))
        for row in report['comparisons']:
            self.assertIsNone(row['same_action_and_selection'])
            self.assertIsNone(row['narrow_case_pass'])

    def test_different_valid_coffee_is_not_an_accuracy_failure(self):
        menus, cases = prepare(self.reference, self.evidence, 'fixture')
        calls = []
        def fixture(payload):
            case = cases[len(calls)]
            calls.append(payload)
            expected = case['evaluation']
            mid = 'cafe_latte' if case['parent_id'] == 'easy_hot_coffee' else expected['acceptable_menu_ids'][0]
            value = {'status': 'recommend', 'requested_menu_name': '', 'recommendations': [{
                'menu_id': mid, 'temperature': expected['hard_constraints']['temperature'],
                'basis_fields': expected['required_basis_fields'] or ['price_krw']}],
                'questions': [], 'unresolved_requirements': [], 'missing_information': []}
            reply = mock_transport(payload)
            reply['output'][0]['content'][0]['text'] = json.dumps(value)
            return reply
        # Injected fixture tests scoring code only; does not make network/API calls.
        report = compare(self.reference, run(menus, self.evidence, cases, 'fixture', fixture, 'live'))
        changed = next(c for c in report['comparisons'] if c['case_id'] == 'replay_easy_hot_coffee')
        self.assertFalse(changed['same_action_and_selection'])
        self.assertTrue(changed['narrow_case_pass'])
        self.assertEqual(len(calls), 10)
        for payload in calls:
            text = json.dumps(payload)
            self.assertNotIn('reference_selection', text)
            self.assertNotIn('acceptable_menu_ids', text)

    def test_errors_not_counted_as_consistent(self):
        self.assertIsNone(signature({'status': 'error', 'origin': 'llm'}))

    def test_paid_gate_before_reference_or_key_read(self):
        result = subprocess.run([sys.executable, '-B', '-m', 'app.experiments.run_stability_v3',
                                 '--mode', 'live', '--model', 'fixture', '--reference', 'does-not-exist',
                                 '--env-file', 'PRIVATE-DO-NOT-READ', '--output-dir', 'unused'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Live requires', result.stderr)
        self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
