import json
import unittest

from app.experiments.compare_recommendations_v2 import compare, mock_transport
from app.experiments.evaluate_recommendations_v2 import evaluate_record, evaluate_result
from app.experiments.menu_evidence import DEFAULT_EVIDENCE
from app.services.recommendation_conditions_v2 import derive_conditions
from test_llm_direct_v2 import fixture_menus, response, selection

DATASET = DEFAULT_EVIDENCE.parent/'v2_accuracy_cases.json'


class AccuracyDatasetTests(unittest.TestCase):
    def setUp(self):
        self.cases = json.loads(DATASET.read_text(encoding='utf-8'))
        self.menus = fixture_menus()
        self.evidence = json.loads(DEFAULT_EVIDENCE.read_text(encoding='utf-8'))

    def test_ten_unique_new_cases_and_evaluation_is_not_prompt_input(self):
        self.assertEqual(len(self.cases), 10)
        self.assertEqual(len({c['id'] for c in self.cases}), 10)
        seen = []
        def capture(payload):
            seen.append(json.loads(payload['input'][0]['content']))
            return mock_transport(payload)
        report = compare(self.menus, self.evidence, self.cases, 1, 'mock', capture, 'mock')
        self.assertEqual(len(seen), 10)
        for data, case in zip(seen, self.cases):
            self.assertEqual(data['transcript'], case['text'])
            self.assertNotIn('evaluation', data)
            self.assertNotIn(case['evaluation']['review_note'], json.dumps(data, ensure_ascii=False))
        self.assertEqual(len(report['evaluation_annotations']), 10)
        self.assertTrue(all(row['methods']['llm_direct_v2']['independent_evaluation']['state'] == 'not_scored_mock' for row in report['runs']))

    def test_new_negation_and_numeric_zero_forms(self):
        self.assertEqual(derive_conditions(self.cases[0]['text'])['max_price_krw'], 3000)
        self.assertEqual(derive_conditions(self.cases[1]['text'])['excluded_categories'], ['커피'])
        self.assertTrue(derive_conditions(self.cases[2]['text'])['milk_free'])
        self.assertEqual(derive_conditions(self.cases[3]['text'])['excluded_categories'], [])
        self.assertEqual(derive_conditions(self.cases[4]['text'])['max_caffeine_mg'], 0)
        self.assertFalse(derive_conditions('우유를 제외하지 마세요')['milk_free'])

    def test_evaluator_catches_constraint_missed_by_model_or_parser(self):
        # These are deliberately wrong fixtures, not live model results.
        case = self.cases[1]
        result = evaluate_result(response(selection('iced_americano')), case, self.menus, self.evidence)
        self.assertIn('EXCLUDED_CATEGORY', result['factual_violations'])
        milk = evaluate_result(response(selection('lemonade')), self.cases[2], self.menus, self.evidence)
        self.assertIn('MILK_NOT_VERIFIED_ABSENT', milk['factual_violations'])
        caffeine = evaluate_result(response(selection('peach_iced_tea')), self.cases[4], self.menus, self.evidence)
        self.assertIn('CAFFEINE_NOT_VERIFIED_WITHIN_LIMIT', caffeine['factual_violations'])

    def test_wrong_budget_temperature_unknown_id_and_duplicate(self):
        cases = [
            (response(selection('lemonade')), 'OVER_BUDGET'),
            (response(selection('espresso', 'HOT')), 'WRONG_TEMPERATURE'),
            (response(selection('invented')), 'UNKNOWN_MENU_ID'),
            (response(selection(), selection()), 'DUPLICATE_MENU_ID')]
        for value, code in cases:
            with self.subTest(code=code):
                self.assertIn(code, evaluate_result(value, self.cases[0], self.menus, self.evidence)['factual_violations'])

    def test_behavior_expectations_are_review_not_subjective_gold(self):
        value = response(selection())
        result = evaluate_result(value, self.cases[5], self.menus, self.evidence)
        self.assertEqual(result['factual_violations'], [])
        self.assertTrue(result['behavior_review_required'])
        self.assertIsNone(result['subjective_quality'])
        question = {'status': 'clarify', 'recommendations': [], 'questions': ['어떤 뒷맛을 원하세요?'], 'missing_information': []}
        self.assertFalse(evaluate_result(question, self.cases[5], self.menus, self.evidence)['behavior_review_required'])

    def test_raw_rejection_is_distinct_from_delivered_result(self):
        record = {'status': 'error', 'rejected_response': response(selection('lemonade'))}
        evaluated = evaluate_record(record, self.cases[0], self.menus, self.evidence, 'live')
        self.assertEqual(evaluated['state'], 'raw_response_rejected_by_server')
        self.assertIn('OVER_BUDGET', evaluated['factual_violations'])
        mock = evaluate_record(record, self.cases[0], self.menus, self.evidence, 'mock')
        self.assertIsNone(mock['factual_violations'])


if __name__ == '__main__':
    unittest.main()
