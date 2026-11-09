import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from app.db.catalog import load_catalog
from app.experiments.compare_recommendations import CASES
from app.experiments.menu_evidence import (DEFAULT_EVIDENCE, export_facts, prepare,
                                           readiness, validate_evidence)
from app.services.llm_direct import DirectError, validate_response


class MenuEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog()
        self.data = json.loads(DEFAULT_EVIDENCE.read_text(encoding='utf-8'))

    def test_actual_evidence_covers_catalog_and_explicit_unknowns(self):
        validate_evidence(self.data, self.catalog)
        r = readiness(self.data)
        self.assertEqual(r['menu_count'], 11)
        self.assertTrue(any('milk' in row['missing'] for row in r['variants']))

    def test_blank_allergen_not_exported_as_absence(self):
        facts = export_facts(self.data)
        lemonade = facts['lemonade']
        self.assertFalse(any('우유' in f['text'] or '알레르기' in f['text'] for f in lemonade))
        self.assertTrue(any('카페인' in f['text'] for f in lemonade))

    def test_no_alias_or_temperature_propagation(self):
        data = copy.deepcopy(self.data)
        # Simulate having only HOT evidence; export must not invent COLD statements.
        for mid in ('lemon_tea', 'citron_tea'):
            row = next(r for r in data['menus'] if r['menu_id'] == mid)
            for record in row['variants']['COLD'].values():
                record.update(status='unknown', value=None, source=None, checked_date=None)
        facts = export_facts(data)
        self.assertEqual(facts['lemon_tea_alias'], [])
        self.assertTrue(all('[HOT에만 적용]' in f['text'] for f in facts['lemon_tea']))
        self.assertTrue(all('[HOT에만 적용]' in f['text'] for f in facts['citron_tea']))

    def test_invalid_assertions_rejected(self):
        for mutation in ('negative_caffeine', 'unknown_value', 'missing_source', 'empty_allergens', 'bad_date', 'duplicate_id'):
            data = copy.deepcopy(self.data)
            fields = data['menus'][0]['variants']['COLD']
            if mutation == 'negative_caffeine': fields['caffeine_mg']['value'] = -1
            elif mutation == 'unknown_value': fields['milk']['value'] = False
            elif mutation == 'missing_source': fields['description']['source'] = None
            elif mutation == 'empty_allergens': fields['allergens']['value'] = []
            elif mutation == 'bad_date': fields['description']['checked_date'] = 'not-a-date'
            else: data['menus'][1] = copy.deepcopy(data['menus'][0])
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                validate_evidence(data, self.catalog)

    def test_prepare_no_constraint_hints_and_no_scores(self):
        menus = [{'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
                  'available_temperatures': [t for t, _ in m.variants], 'categories': list(m.categories),
                  'is_available': True} for m in self.catalog]
        enriched, requests = prepare(self.data, menus, CASES, 'not-configured')
        user = json.loads(requests[0]['request']['input'][0]['content'])
        self.assertEqual(set(user), {'transcript', 'menus'})
        self.assertTrue(requests[0]['server_constraints'])
        self.assertTrue(enriched[0]['verified_facts'])
        self.assertNotIn('continuous.csv', json.dumps(requests))
        candidate = {'status': 'recommend', 'recommendations': [{'menu_id': 'peach_iced_tea',
                    'temperature': 'COLD', 'reason': '3000원인 등록 메뉴입니다.'}], 'questions': [], 'missing_information': []}
        validate_response(candidate, enriched, CASES[0]['constraints'])
        candidate['recommendations'][0]['menu_id'] = 'iced_americano'
        with self.assertRaisesRegex(DirectError, 'CONSTRAINT_VIOLATION'):
            validate_response(candidate, enriched, CASES[0]['constraints'])

    def test_cli_offline_bundle_and_handwritten_response(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            response = root / 'response.json'
            response.write_text(json.dumps({'status': 'clarify', 'recommendations': [],
                'questions': ['커피 종류를 모두 제외할까요?'], 'missing_information': []}), encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', '-m', 'app.experiments.menu_evidence',
                '--catalog-fixture', '--response', str(response), '--output-dir', str(root/'bundle')],
                capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            report = json.loads((root/'bundle/readiness.json').read_text(encoding='utf-8'))
            self.assertEqual(report['paid_calls'], 0)
            self.assertTrue(report['synthetic_availability'])
            self.assertTrue(report['manual_response_check']['accepted'])
            self.assertFalse(report['constraint_hints_sent_to_model'])


if __name__ == '__main__':
    unittest.main()
