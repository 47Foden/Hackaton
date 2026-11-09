import copy
import json
from pathlib import Path
import tempfile
import unittest

from app.experiments.compare_recommendations import CASES
from app.experiments.compare_recommendations_v2 import compare, mock_transport
from app.experiments.menu_evidence import DEFAULT_EVIDENCE
from app.services import llm_direct_v2 as v2
from app.services.llm_direct import DirectError
from app.services.sensory_tags import DEFAULT_TABLE, evidence_digest, load_annotations
from test_llm_direct_v2 import fixture_menus, selection, response, envelope


class SensoryTagsTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(DEFAULT_EVIDENCE.read_text(encoding='utf-8'))
        self.menus = fixture_menus()

    def test_table_is_editorial_not_gold_and_covers_all_variants(self):
        table = load_annotations(self.evidence)
        self.assertIs(table['is_gold_standard'], False)
        self.assertEqual(len(table['profiles']), 16)
        self.assertEqual(len({r['menu_id'] for r in table['profiles']}), 11)
        self.assertTrue(all(r['tags']['lingering_sweetness']['state'] == 'unknown' for r in table['profiles']))
        self.assertTrue(all(r['tags']['astringent']['state'] == 'unknown' for r in table['profiles']))

    def test_no_name_or_alias_inference_without_description(self):
        table = load_annotations(self.evidence)
        for row in table['profiles']:
            if row['menu_id'] in ('lemon_tea_alias', 'iced_americano'):
                self.assertTrue(all(t['state'] == 'unknown' for t in row['tags'].values()))

    def test_cannot_promote_subjective_tag_to_verified_fact(self):
        table = json.loads(DEFAULT_TABLE.read_text(encoding='utf-8'))
        row = next(r for r in table['profiles'] if r['menu_id'] == 'lemonade')
        row['tags']['refreshing']['state'] = 'supported'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'annotations.json'
            path.write_text(json.dumps(table), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Subjective texture'):
                load_annotations(self.evidence, path)

    def test_changed_menu_evidence_requires_editorial_review(self):
        changed = copy.deepcopy(self.evidence)
        changed['menus'][0]['variants']['COLD']['description']['value'] = 'changed description'
        with self.assertRaisesRegex(ValueError, 'must match evidence'):
            load_annotations(changed)

    def test_subjective_request_reaches_llm_by_default(self):
        calls = []
        def ask(payload):
            calls.append(payload)
            return envelope({'status': 'clarify', 'recommendations': [],
                             'questions': ['원하는 깔끔함은 산미/탄산 쪽인가요, 단맛이 적은 뒷맛 쪽인가요?'],
                             'missing_information': []})
        result = v2.recommend(CASES[2]['text'], self.menus, self.evidence, 'mock', ask)
        self.assertEqual(result['origin'], 'llm')
        self.assertEqual(len(calls), 1)
        data = json.loads(calls[0]['input'][0]['content'])
        self.assertEqual(data['transcript'], CASES[2]['text'])
        self.assertEqual(len(data['menus']), 11)
        self.assertIs(data['sensory']['is_gold_standard'], False)
        self.assertEqual(data['sensory']['annotation_sha256'], evidence_digest(load_annotations(self.evidence)))
        self.assertTrue(all(a['state'] != 'unknown' for a in data['sensory']['annotations'].values()))
        self.assertTrue(all('lingering_sweetness' in variant['unknown_sensory_tags']
                            for menu in data['menus'] for variant in menu['variants']))

    def test_milk_unknown_also_reaches_model_but_cannot_be_recommended(self):
        def choose(payload):
            return envelope(response(selection('lemonade')))
        with self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
            v2.recommend('우유 들어간 건 빼주세요', self.menus, self.evidence, 'mock', choose)
        result = v2.recommend('우유 들어간 건 빼주세요', self.menus, self.evidence, 'mock',
            lambda _: envelope({'status': 'insufficient_data', 'recommendations': [], 'questions': [],
                                'missing_information': ['우유 미포함이 명시된 성분 자료가 필요합니다.']}))
        self.assertEqual(result['origin'], 'llm')

    def test_inferred_tag_is_labeled_and_requires_its_basis_fact(self):
        context = v2.prepare_context('깔끔하게 마실 음료', self.menus, self.evidence)
        result = v2.validate_response(response(selection('lemonade', fit='refreshing', fields=('description',))), context)
        self.assertIn('추론 가설(실측 아님)', result['recommendations'][0]['reason'])
        value = response(selection('lemonade', fields=('price_krw',)))
        value['recommendations'][0]['matched_tag_ids'] = ['tag:lemonade:COLD:refreshing']
        with self.assertRaisesRegex(DirectError, 'TAG_BASIS_REQUIRED'):
            v2.validate_response(value, context)

    def test_unrelated_description_no_longer_justifies_refreshing(self):
        context = v2.prepare_context('깔끔한 음료', self.menus, self.evidence)
        # Cafe latte has a verified description, but no supported/inferred refreshing annotation.
        with self.assertRaisesRegex(DirectError, 'UNKNOWN_TAG_IS_NOT_EVIDENCE'):
            v2.validate_response(response(selection('cafe_latte', 'HOT', 'refreshing', ('description',))), context)

    def test_sweet_does_not_prove_nonsticky_and_unknown_tag_is_rejected(self):
        context = v2.prepare_context('달지만 끈적하지 않게', self.menus, self.evidence)
        value = response(selection(fields=('description',), fit='sweet'))
        value['recommendations'][0]['matched_tag_ids'].append('tag:peach_iced_tea:COLD:lingering_sweetness')
        with self.assertRaisesRegex(DirectError, 'UNKNOWN_TAG_IS_NOT_EVIDENCE'):
            v2.validate_response(value, context)

    def test_tag_from_another_menu_or_temperature_is_rejected(self):
        context = v2.prepare_context('추천', self.menus, self.evidence)
        value = response(selection('cafe_latte', 'COLD', fields=('description',)))
        for tid in ('tag:lemonade:COLD:refreshing', 'tag:cafe_latte:HOT:rich'):
            value['recommendations'][0]['matched_tag_ids'] = [tid]
            with self.subTest(tid=tid), self.assertRaisesRegex(DirectError, 'TAG_SCOPE_MISMATCH'):
                v2.validate_response(value, context)

    def test_direct_comparison_never_routes_to_server_questions(self):
        report = compare(self.menus, self.evidence, CASES, 1, 'mock', mock_transport, 'mock')
        outputs = [row['methods']['llm_direct_v2'] for row in report['runs']]
        self.assertTrue(all(r['origin'] == 'mock_fixture' for r in outputs))
        self.assertEqual(sum(r['transport_calls'] for r in outputs), 5)
        self.assertEqual(sum(r['api_calls'] for r in outputs), 0)
        self.assertEqual(report['decision_mode'], 'llm')
        self.assertEqual(report['candidate_mode'], 'full')


if __name__ == '__main__':
    unittest.main()
