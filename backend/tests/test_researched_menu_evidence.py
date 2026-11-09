import json
import unittest

from app.db.catalog import load_catalog
from app.experiments.menu_evidence import DEFAULT_EVIDENCE, validate_evidence
from app.services.sensory_tags import RESEARCHED_EVIDENCE, RESEARCHED_TABLE, load_annotations
from app.services import llm_direct_v2 as v2
from app.services.llm_direct import DirectError
from test_llm_direct_v2 import fixture_menus, response, selection


class ResearchedEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.old = json.loads(DEFAULT_EVIDENCE.read_text(encoding='utf-8'))
        self.new = json.loads(RESEARCHED_EVIDENCE.read_text(encoding='utf-8'))
        self.table = load_annotations(self.new)

    def test_both_snapshots_validate_and_select_matching_annotations(self):
        for evidence in (self.old, self.new):
            validate_evidence(evidence, load_catalog())
            self.assertFalse(load_annotations(evidence)['is_gold_standard'])
        self.assertEqual(self.table['version'], 'sensory-researched-v2.2')
        self.assertNotEqual(load_annotations(self.old)['version'], self.table['version'])
        with self.assertRaisesRegex(ValueError, 'must match evidence'):
            load_annotations(self.old, RESEARCHED_TABLE)

    def test_hot_green_tea_verified_without_guessing_caffeine(self):
        row = next(m for m in self.new['menus'] if m['menu_id'] == 'green_tea_latte')
        for temp in ('HOT', 'COLD'):
            fields = row['variants'][temp]
            self.assertEqual(fields['description']['status'], 'verified')
            self.assertIs(fields['milk']['value'], True)
            self.assertEqual(fields['caffeine_mg']['status'], 'unknown')
            self.assertIsNone(fields['caffeine_mg']['value'])

    def test_shop_description_is_not_official_nutrition_or_milk_absence(self):
        row = next(m for m in self.new['menus'] if m['menu_id'] == 'iced_americano')['variants']['COLD']
        self.assertIn('app.passorder.co.kr', row['description']['source'])
        self.assertEqual(row['description']['status'], 'verified')
        self.assertEqual(row['caffeine_mg']['status'], 'unknown')
        self.assertEqual(row['milk']['status'], 'unknown')

    def test_sugar_is_only_a_sweetness_hypothesis_not_finish(self):
        for row in self.table['profiles']:
            if row['menu_id'] in ('lemon_tea', 'lemonade', 'green_tea_latte'):
                self.assertEqual(row['tags']['sweet']['state'], 'inferred')
            self.assertEqual(row['tags']['lingering_sweetness']['state'], 'unknown')
            self.assertEqual(row['tags']['astringent']['state'], 'unknown')

    def test_alias_not_filled_and_no_milk_false_claim_invented(self):
        alias = next(m for m in self.new['menus'] if m['menu_id'] == 'lemon_tea_alias')
        self.assertTrue(all(f['status'] == 'unknown' for fields in alias['variants'].values() for f in fields.values()))
        self.assertFalse(any(fields['milk']['value'] is False for m in self.new['menus'] for fields in m['variants'].values()))

    def test_researched_tag_can_be_selected_only_with_labeled_inference(self):
        context = v2.prepare_context('단맛 있는 음료', fixture_menus(), self.new)
        result = v2.validate_response(response(selection('lemonade', fit='sweet', fields=('description',))), context)
        self.assertIn('53.6g', result['recommendations'][0]['reason'])
        self.assertIn('추론 가설(실측 아님)', result['recommendations'][0]['reason'])

    def test_researched_zero_caffeine_still_excludes_ambiguous_green_tea(self):
        context = v2.prepare_context('카페인 없는 음료', fixture_menus(), self.new)
        with self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
            v2.validate_response(response(selection('green_tea_latte', 'HOT')), context)


if __name__ == '__main__':
    unittest.main()
