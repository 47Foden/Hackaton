import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.experiments.recorded_transport import recorded_transport
from app.experiments.menu_evidence import DEFAULT_EVIDENCE
from app.services.llm_direct import DirectError


class RecordedTransportTests(unittest.TestCase):
    def test_cap_no_retries_and_only_response_is_journaled(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory)/'api-attempts.json'
            calls = []
            def mock(payload):
                calls.append(payload)
                return {'status': 'completed', 'usage': {'input_tokens': 10}, 'output': []}
            send = recorded_transport(mock, journal, 2)
            for _ in range(2):
                send({'model': 'gpt-5.4-mini-2026-03-17', 'input': 'PRIVATE-TEST-PROMPT'})
            with self.assertRaisesRegex(DirectError, 'CALL_LIMIT_REACHED'):
                send({'model': 'mock'})
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0]['reasoning'], {'effort': 'none'})
            text = journal.read_text(encoding='utf-8')
            self.assertNotIn('PRIVATE-TEST-PROMPT', text)
            data = json.loads(text)
            self.assertEqual(data['retries'], 0)
            self.assertEqual(len(data['calls']), 2)
            self.assertEqual(data['calls'][0]['response']['usage']['input_tokens'], 10)

    def test_attempt_is_saved_before_transport_and_rerun_is_blocked(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory)/'api-attempts.json'
            def interrupted(payload):
                self.assertEqual(json.loads(journal.read_text(encoding='utf-8'))['calls'][0]['state'], 'started')
                raise KeyboardInterrupt('SENSITIVE-TEST-ERROR')
            send = recorded_transport(interrupted, journal, 1)
            with self.assertRaises(KeyboardInterrupt):
                send({'model': 'mock'})
            self.assertNotIn('SENSITIVE-TEST-ERROR', journal.read_text(encoding='utf-8'))
            with self.assertRaisesRegex(DirectError, 'PREVIOUS_ATTEMPT_EXISTS'):
                recorded_transport(lambda _: self.fail('No retry allowed'), journal, 1)

    def test_safe_provider_error_is_recorded_without_retry(self):
        with tempfile.TemporaryDirectory() as directory:
            journal = Path(directory)/'api-attempts.json'
            def failed(payload):
                raise DirectError('PROVIDER_HTTP_429')
            send = recorded_transport(failed, journal, 1)
            with self.assertRaisesRegex(DirectError, 'PROVIDER_HTTP_429'):
                send({'model': 'mock'})
            data = json.loads(journal.read_text(encoding='utf-8'))
            self.assertEqual(len(data['calls']), 1)
            self.assertEqual(data['calls'][0]['error_code'], 'PROVIDER_HTTP_429')

    def test_cli_budget_gate_precedes_private_file_read(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, '-B', '-m', 'app.experiments.compare_recommendations_v2',
                '--v1-report', str(DEFAULT_EVIDENCE.parents[3]/'docs/experiments/2026-11-09-first-live/results.json'),
                '--cases', str(DEFAULT_EVIDENCE.parent/'v2_accuracy_cases.json'),
                '--mode', 'live', '--allow-paid-api', '--env-file', 'DO-NOT-READ', '--model', 'mock',
                '--max-api-calls', '1', '--output-dir', directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('exceed --max-api-calls', result.stderr)

    def test_cli_existing_attempt_precedes_private_file_read(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'api-attempts.json').write_text('{}', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', '-m', 'app.experiments.compare_recommendations_v2',
                '--v1-report', str(DEFAULT_EVIDENCE.parents[3]/'docs/experiments/2026-11-09-first-live/results.json'),
                '--mode', 'live', '--allow-paid-api', '--env-file', 'DO-NOT-READ', '--model', 'mock',
                '--output-dir', directory], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn('A paid attempt already exists', result.stderr)


if __name__ == '__main__':
    unittest.main()
