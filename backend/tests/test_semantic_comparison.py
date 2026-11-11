import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.evaluation.compare_semantic_direct import compare
from app.services import llm_direct as previous


class SemanticComparisonTests(unittest.TestCase):
    def test_eight_free_mock_paths_do_not_call_real_transport_or_claim_quality(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(previous, 'openai_transport', side_effect=AssertionError('No paid API')):
            report = compare(Path(folder), 'mock')
            self.assertEqual(len(report['cases']), 4)
            self.assertEqual(report['paid_api_calls'], 0)
            self.assertFalse(report['quality_measured'])
            self.assertEqual(len(list((Path(folder)/'requests').glob('*.json'))), 8)
            self.assertEqual(sum(row[name]['mock_transport_calls'] for row in report['cases']
                                 for name in ('previous', 'semantic')), 8)
            joint = next(row for row in report['cases'] if row['id'] == 'joint_exclusion')
            self.assertEqual(joint['previous']['eligible_ids'], [])
            self.assertIn('strawberry_latte', joint['semantic']['visible_available_ids'])
            self.assertEqual(joint['semantic']['fixture_validation'], 'accepted')
            self.assertEqual(json.loads((Path(folder)/'results.json').read_text(encoding='utf-8'))['paid_api_calls'], 0)

    def test_request_only_does_not_execute_even_mock_transport(self):
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(previous, 'recommend', side_effect=AssertionError('No recommendation execution')):
            report = compare(Path(folder), 'request')
            self.assertTrue(all(row[name]['mock_transport_calls'] == 0 for row in report['cases']
                                for name in ('previous', 'semantic')))
