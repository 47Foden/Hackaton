import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.db.catalog import load_catalog
from app.experiments.run_small_experiment import bounded_transport, load_user_key, run, save_report, resume_run
from app.services.llm_direct import DirectError


class SmallExperimentTests(unittest.TestCase):
    def setUp(self):
        self.menus = [{'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
            'categories': list(m.categories), 'available_temperatures': [t for t, _ in m.variants],
            'is_available': True} for m in load_catalog()]

    def test_fixed_six_call_limit_and_no_constraint_hints(self):
        requests = []
        def transport(payload):
            requests.append(payload)
            result = {'status': 'clarify', 'recommendations': [], 'questions': ['취향을 더 알려주세요.'], 'missing_information': []}
            return {'status': 'completed', 'usage': {'input_tokens': 100, 'output_tokens': 20},
                'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(result)}]}]}
        report = run(self.menus, transport, 'mock', [0.75, 0.075, 4.5])
        self.assertEqual(len(requests), 6)
        self.assertEqual(len(report['comparison']['runs']), 5)
        self.assertEqual(set(json.loads(requests[0]['input'][0]['content'])), {'transcript', 'menus'})
        self.assertEqual(requests[0]['reasoning'], {'effort': 'none'})

    def test_stop_on_smoke_failure_preserves_usage(self):
        calls = []
        def fail(payload):
            calls.append(payload)
            return {'status': 'incomplete', 'usage': {'input_tokens': 100, 'output_tokens': 1800}}
        report = run(self.menus, fail, 'mock', [0.75, 0.075, 4.5])
        self.assertEqual(len(calls), 1)
        self.assertIsNone(report['comparison'])
        record = report['smoke']['runs'][0]['methods']['llm_direct']
        self.assertEqual(record['usage']['output_tokens'], 1800)
        self.assertGreater(record['cost_usd_estimate'], 0)
        with tempfile.TemporaryDirectory() as directory:
            save_report(report, Path(directory))
            self.assertTrue((Path(directory)/'results.ko.md').is_file())

    def test_credential_loader_only_on_temp_fixture_no_interpolation(self):
        # This test never opens the user's backend/.env.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.env'
            path.write_text('OPENAI_API_KEY="fake-${NOT_EXPANDED}"\nOTHER_SETTING=unused\n', encoding='utf-8')
            self.assertEqual(load_user_key(path), 'fake-${NOT_EXPANDED}')

    def test_bounded_transport_rejects_seventh_call(self):
        send = bounded_transport(lambda _: {})
        for _ in range(6):
            send({})
        with self.assertRaisesRegex(DirectError, 'CALL_LIMIT_REACHED'):
            send({})

    def test_live_gate_before_menu_or_key_access(self):
        result = subprocess.run([sys.executable, '-B', '-m', 'app.experiments.run_small_experiment',
            '--mode', 'live', '--env-file', 'nonexistent-private-file', '--rates', '0.75', '0.075', '4.5',
            '--output-dir', 'unused-test-output'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('Live requires', result.stderr)

    def test_resume_received_constraint_failure_only_calls_five_times(self):
        candidate = {'status': 'recommend', 'recommendations': [{'menu_id': 'lemonade',
                     'temperature': 'COLD', 'reason': 'Fixture'}], 'questions': [], 'missing_information': []}
        def invalid(payload):
            return {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(candidate)}]}]}
        rates = [0.75, 0.075, 4.5]
        original = run(self.menus, invalid, 'mock', rates)
        self.assertTrue(original['stopped_after_smoke_error'])
        calls = []
        def clarify(payload):
            calls.append(payload)
            result = {'status': 'clarify', 'recommendations': [], 'questions': ['취향은요?'], 'missing_information': []}
            return {'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(result)}]}]}
        resumed = resume_run(original, clarify, 'mock', rates)
        self.assertEqual(len(calls), 5)
        self.assertEqual(resumed['smoke'], original['smoke'])
        self.assertIsNone(original['comparison'])
        with self.assertRaises(DirectError):
            resume_run(resumed, clarify, 'mock', rates)

    def test_resume_rejects_network_failure_without_transport(self):
        rates = [0.75, 0.075, 4.5]
        original = run(self.menus, lambda _: {'status': 'incomplete'}, 'mock', rates)
        with self.assertRaisesRegex(DirectError, 'RESUME_REQUIRES_RECEIVED_RESPONSE'):
            resume_run(original, lambda _: self.fail('Transport must not be called'), 'mock', rates)


if __name__ == '__main__':
    unittest.main()
