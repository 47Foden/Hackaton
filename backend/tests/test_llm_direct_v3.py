import json
import unittest
from unittest.mock import patch

from app.db.catalog import load_catalog
from app.services import llm_direct_v3 as v3
from app.services.llm_direct import DirectError
from app.services.sensory_tags import RESEARCHED_EVIDENCE
from app.experiments.check_recommendations_v3 import inspect


def candidate(mid='peach_iced_tea', temperature='COLD', fields=None):
    return {'status': 'recommend', 'requested_menu_name': '',
            'recommendations': [{'menu_id': mid, 'temperature': temperature,
                                 'basis_fields': fields or ['price_krw']}],
            'questions': [], 'unresolved_requirements': [], 'missing_information': []}


def question(name=''):
    return {'status': 'clarify', 'requested_menu_name': name,
            'recommendations': [], 'questions': ['목록에 있는 다른 음료를 추천해도 될까요?'],
            'unresolved_requirements': ['요청한 상품 확인'], 'missing_information': []}


def envelope(value):
    return {'status': 'completed', 'usage': {'input_tokens': 10, 'output_tokens': 10},
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


class DirectV3Tests(unittest.TestCase):
    def setUp(self):
        self.menus = [{'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
                       'is_available': True, 'categories': list(m.categories),
                       'available_temperatures': [t for t, _ in m.variants]} for m in load_catalog()]
        # Actual repository identities/prices; availability is SYNTHETIC test data.
        self.evidence = json.loads(RESEARCHED_EVIDENCE.read_text(encoding='utf-8'))

    def context(self, text='추천해 주세요'):
        return v3.prepare_context(text, self.menus, self.evidence)

    def test_request_has_no_fit_long_ids_editorial_hypotheses_or_scores(self):
        request = v3.build_request(self.context(), 'mock-model')
        data = json.loads(request['input'][0]['content'])
        self.assertEqual(set(data), {'transcript', 'menus', 'guard_hints'})
        text = json.dumps(data)
        for absent in ('matched_tag_ids', 'basis_fact_ids', 'sensory', 'continuous.csv', 'fit'):
            self.assertNotIn(absent, text)
        self.assertFalse(request['store'])
        schema = request['text']['format']['schema']
        rec = schema['properties']['recommendations']
        self.assertEqual(rec['maxItems'], 1)
        self.assertEqual(rec['items']['properties']['basis_fields']['items']['enum'], v3.FIELDS)

    def test_valid_price_choice_attaches_real_facts(self):
        result = v3.validate_response(candidate(), self.context('3000원 이하 차가운 음료'))
        self.assertEqual(result['recommendations'][0]['evidence'][0]['value'], 3000)

    def test_budget_and_temperature_are_rechecked(self):
        for text, selection in [('2500원 이하', candidate()),
                                ('따뜻한 음료', candidate())]:
            with self.subTest(text=text), self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
                v3.validate_response(selection, self.context(text))

    def test_unavailable_menu_rejected(self):
        next(m for m in self.menus if m['menu_id'] == 'peach_iced_tea')['is_available'] = False
        with self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
            v3.validate_response(candidate(), self.context())

    def test_unknown_id_rejected(self):
        with self.assertRaisesRegex(DirectError, 'UNKNOWN_MENU_ID'):
            v3.validate_response(candidate('invented'), self.context())

    def test_unknown_milk_does_not_become_milk_free(self):
        with self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
            v3.validate_response(candidate(), self.context('우유는 안 돼요'))

    def test_coffee_does_not_require_artificial_caffeine_fit(self):
        result = v3.validate_response(candidate('iced_americano'), self.context('커피를 제외하지 마세요. 2500원 이하'))
        self.assertEqual(result['recommendations'][0]['menu_id'], 'iced_americano')

    def test_zero_caffeine_rechecked_without_copied_fact_ids(self):
        context = self.context('카페인 0mg인 차가운 음료')
        v3.validate_response(candidate('lemonade', fields=['caffeine_mg']), context)
        with self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
            v3.validate_response(candidate('iced_americano'), context)

    def test_unknown_fields_cannot_be_used_as_evidence(self):
        with self.assertRaisesRegex(DirectError, 'EVIDENCE_SCOPE_MISMATCH'):
            v3.validate_response(candidate(fields=['milk']), self.context())

    def test_short_description_basis_no_tag_copy(self):
        value = candidate('lemonade', fields=['description'])
        result = v3.validate_response(value, self.context('레몬 산미와 탄산이 좋아요'))
        self.assertIn('확인된 설명', result['recommendations'][0]['reason'])

    def test_absent_requested_menu_requires_question(self):
        value = candidate('cafe_latte', temperature='HOT')
        value['requested_menu_name'] = '바닐라 오트라떼'
        with self.assertRaisesRegex(DirectError, 'UNKNOWN_REQUESTED_MENU_REQUIRES_QUESTION'):
            v3.validate_response(value, self.context())
        self.assertEqual(v3.validate_response(question('바닐라 오트라떼'), self.context())['status'], 'clarify')

    def test_known_requested_menu_cannot_be_substituted(self):
        value = candidate()
        value['requested_menu_name'] = '레몬에이드'
        with self.assertRaisesRegex(DirectError, 'REQUESTED_MENU_MISMATCH'):
            v3.validate_response(value, self.context())

    def test_unresolved_finish_prevents_recommendation(self):
        value = candidate('lemonade')
        value['unresolved_requirements'] = ['단맛 잔류 자료 미확인']
        with self.assertRaisesRegex(DirectError, 'UNRESOLVED_RECOMMENDATION'):
            v3.validate_response(value, self.context())

    def test_two_candidates_and_multiple_questions_rejected(self):
        value = candidate()
        value['recommendations'] *= 2
        with self.assertRaisesRegex(DirectError, 'INVALID_RECOMMENDATIONS'):
            v3.validate_response(value, self.context())
        value = question()
        value['questions'] *= 2
        with self.assertRaisesRegex(DirectError, 'INVALID_RESPONSE'):
            v3.validate_response(value, self.context())

    def test_malformed_basis_and_empty_clarification_rejected(self):
        for fields in [['price_krw', 'price_krw'], ['tag:refreshing'], [None]]:
            with self.subTest(fields=fields), self.assertRaises(DirectError):
                v3.validate_response(candidate(fields=fields), self.context())
        value = question()
        value['questions'] = []
        with self.assertRaisesRegex(DirectError, 'MISSING_QUESTION'):
            v3.validate_response(value, self.context())

    def test_mock_transport_and_errors_preserve_usage_without_retry(self):
        calls = []
        def mock(payload):
            calls.append(payload)
            return envelope(candidate('invented'))
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            with self.assertRaises(DirectError) as error:
                v3.recommend('추천', self.menus, self.evidence, 'mock', mock)
        self.assertEqual(len(calls), 1)
        self.assertEqual(error.exception.usage['input_tokens'], 10)
        self.assertEqual(error.exception.candidate_response, candidate('invented'))

    def test_refusal_and_incomplete_are_errors(self):
        for reply, code in [({'status': 'incomplete'}, 'INCOMPLETE_RESPONSE'),
                            ({'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]}, 'PROVIDER_REFUSAL')]:
            with self.subTest(code=code), self.assertRaisesRegex(DirectError, code):
                v3.recommend('추천', self.menus, self.evidence, 'mock', lambda _: reply)

    def test_offline_report_never_reads_key_or_calls_network(self):
        with patch('urllib.request.urlopen', side_effect=AssertionError('No network')):
            report = inspect(self.menus, self.evidence, [{'id': 'test', 'text': '추천'}])
        row = report['runs'][0]
        self.assertEqual(row['origin'], 'mock_fixture')
        self.assertEqual(row['api_calls'], 0)
        self.assertIsNone(row['llm_quality'])
        self.assertLess(row['input_characters_v3'], row['input_characters_v2'])


if __name__ == '__main__':
    unittest.main()
