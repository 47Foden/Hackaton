import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from app.experiments.run_easy_v3 import CASES_PATH, ROOT, run, save, mock_transport
from app.services.sensory_tags import RESEARCHED_EVIDENCE


class EasyV3Tests(unittest.TestCase):
    def setUp(self):
        self.menus = json.loads((ROOT/'docs/experiments/2026-11-09-first-live/results.json').read_text(encoding='utf-8'))['smoke']['catalog']
        self.evidence = json.loads(RESEARCHED_EVIDENCE.read_text(encoding='utf-8'))
        self.cases = json.loads(CASES_PATH.read_text(encoding='utf-8'))

    def test_mock_not_scored_and_no_network(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            report = run(self.menus, self.evidence, self.cases, 'mock', mock_transport, 'mock')
        self.assertEqual(len(report['runs']), 5)
        for row in report['runs']:
            self.assertEqual(row['v3']['api_calls'], 0)
            self.assertIsNone(row['v3']['evaluation']['narrow_case_pass'])
            self.assertIsNone(row['v3']['cost_usd_estimate'])

    def test_structural_fixture_has_no_evaluator_leak(self):
        calls = []
        def fixture(payload):
            calls.append(payload)
            case = self.cases[len(calls)-1]
            fields = case['evaluation']['required_basis_fields'] or ['price_krw']
            value = {'status': 'recommend', 'requested_menu_name': '',
                     'recommendations': [{'menu_id': case['evaluation']['acceptable_menu_ids'][0],
                                          'temperature': case['evaluation']['hard_constraints']['temperature'],
                                          'basis_fields': fields}],
                     'questions': [], 'unresolved_requirements': [], 'missing_information': []}
            reply = mock_transport(payload)
            reply['output'][0]['content'][0]['text'] = json.dumps(value)
            return reply
        # "live" exercises scoring code with an injected local fixture, not a real API.
        report = run(self.menus, self.evidence, self.cases, 'test-fixture', fixture, 'live')
        self.assertTrue(all(r['v3']['evaluation']['narrow_case_pass'] for r in report['runs']))
        for request in calls:
            text = json.dumps(request)
            for field in ('acceptable_menu_ids', 'required_basis_fields', 'rationale', 'evaluation'):
                self.assertNotIn('"'+field+'"', text)

    def test_error_and_rejected_response_preserved(self):
        def bad(payload):
            reply = mock_transport(payload)
            value = json.loads(reply['output'][0]['content'][0]['text'])
            value.update(status='recommend', recommendations=[{'menu_id': 'invented', 'temperature': 'COLD', 'basis_fields': ['price_krw']}], missing_information=[])
            reply['output'][0]['content'][0]['text'] = json.dumps(value)
            return reply
        report = run(self.menus, self.evidence, self.cases[:1], 'test', bad, 'live')
        row = report['runs'][0]['v3']
        self.assertEqual(row['error_code'], 'UNKNOWN_MENU_ID')
        self.assertIsNotNone(row['rejected_response'])
        self.assertFalse(row['evaluation']['narrow_case_pass'])

    def test_report_is_explicit_about_mock_and_limits(self):
        report = run(self.menus, self.evidence, self.cases, 'mock', mock_transport, 'mock')
        with tempfile.TemporaryDirectory() as tmp:
            save(report, Path(tmp))
            text = (Path(tmp)/'report.ko.md').read_text(encoding='utf-8')
        for phrase in ('무료 mock', '미측정', '단점', '반복 일관성', '기존 방식'):
            self.assertIn(phrase, text)

    def test_live_gate_before_private_file_access(self):
        result = subprocess.run([sys.executable, '-B', '-m', 'app.experiments.run_easy_v3',
                                 '--mode', 'live', '--v1-report', 'does-not-exist',
                                 '--env-file', 'PRIVATE-DO-NOT-READ', '--output-dir', 'unused'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Live requires', result.stderr)
        self.assertNotIn('Traceback', result.stderr)

    def test_existing_output_blocks_before_reading_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-B', '-m', 'app.experiments.run_easy_v3',
                                     '--v1-report', 'does-not-exist', '--output-dir', tmp],
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('already exists', result.stderr)


if __name__ == '__main__':
    unittest.main()
