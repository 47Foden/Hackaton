"""Replay real v1 failures without pretending the model was called again."""
import copy
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

from pydantic import ValidationError

from app.evaluation import compare_semantic_direct as comparison
from app.services import llm_semantic_direct as semantic
from app.services import llm_direct as previous
from test_semantic_direct import reply, wire


class SemanticV2Regressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows=comparison.catalogue_fixture()
        cls.evidence=json.loads(previous.DEFAULT_EVIDENCE.read_text(encoding='utf-8'))
        cls.fixture=json.loads(Path(comparison.__file__).with_name('semantic_v1_live_cases.json').read_text(encoding='utf-8'))

    def context(self,text='추천'):
        return semantic.prepare_context(text,self.rows,self.evidence)

    def actual(self,task_id):
        return copy.deepcopy(next(row for row in self.fixture['cases'] if row['task_id']==task_id))

    def test_actual_two_successes_keep_same_model_order(self):
        for task_id in ('simple_exclusion.semantic','joint_exclusion.semantic'):
            row=self.actual(task_id)
            result=semantic.validate_response(wire(row['raw_candidate']),self.context(row['text']))
            self.assertEqual([r['menu_id'] for r in result['recommendations']],
                             [r['menu_id'] for r in row['raw_candidate']['recommendations']])
            self.assertEqual(result['normalizations'],[])

    def test_actual_duplicate_is_removed_and_raw_violation_preserved(self):
        row=self.actual('positive_control.semantic'); original=copy.deepcopy(row['raw_candidate'])
        result=semantic.validate_response(wire(row['raw_candidate']),self.context(row['text']))
        self.assertEqual(len(original['recommendations']),6)
        self.assertEqual(len(result['recommendations']),5)
        self.assertEqual(result['raw_contract_issues'],['DUPLICATE_MENU_ID'])
        self.assertEqual(result['normalizations'],[{'kind':'duplicate_menu_id_removed',
            'menu_id':'strawberry_cookie_frappe','kept_input_index':4,'removed_input_index':5}])
        self.assertEqual(row['raw_candidate'],original)

    def test_actual_unresolved_response_is_not_laundered_into_success(self):
        row=self.actual('double_negation.semantic'); original=copy.deepcopy(row['raw_candidate'])
        with self.assertRaisesRegex(semantic.DirectError,'UNRESOLVED_RECOMMENDATION'):
            semantic.validate_response(wire(row['raw_candidate']),self.context(row['text']))
        self.assertEqual(row['raw_candidate'],original)

    def test_unsafe_duplicates_are_validated_before_dropping(self):
        for change,code in [({'option_ids':['invented']},'INVALID_OPTION'),
                            ({'basis_fields':['milk']},'UNKNOWN_BASIS_FACT'),
                            ({'temperature':'HOT'},'INELIGIBLE_OPTION')]:
            value=reply(); value['recommendations'].append({**value['recommendations'][0],**change})
            with self.subTest(change=change),self.assertRaisesRegex(semantic.DirectError,code):
                semantic.validate_response(wire(value),self.context())

    def test_duplicate_same_id_different_valid_temperature_is_conflict(self):
        value=reply('iced_americano')
        value['recommendations'].append({**value['recommendations'][0],'temperature':'HOT'})
        with self.assertRaisesRegex(semantic.DirectError,'DUPLICATE_MENU_CONFLICT'):
            semantic.validate_response(wire(value),self.context())

    def test_requested_count_applies_to_unique_candidates_without_reranking(self):
        value=reply(); value['recommendations'].append(copy.deepcopy(value['recommendations'][0]))
        value['constraints']=[{'kind':'max_recommendations','value':1,'source_text':'하나'}]
        result=semantic.validate_response(wire(value),self.context('하나 추천'))
        self.assertEqual(len(result['recommendations']),1)
        self.assertEqual(result['recommendations'][0]['menu_id'],'strawberry_latte')

    def test_schema_forbids_recommend_with_unknowns_and_data_status_with_candidates(self):
        value=reply(); value['unresolved_requirements']=['실제 미해결 조건']
        with self.assertRaises(ValidationError): semantic.Reply.model_validate(wire(value))
        value=reply(); value['status']='insufficient_data'; value['missing_information']=['확인 자료']
        with self.assertRaises(ValidationError): semantic.Reply.model_validate(wire(value))
        schema=semantic.Reply.model_json_schema()
        self.assertIn('anyOf',schema['properties']['decision'])
        self.assertNotIn('anyOf',schema)

    def test_insufficient_data_stays_insufficient_data(self):
        value=reply()
        value.update(status='insufficient_data',recommendations=[],missing_information=['확인된 전체 성분 자료 필요'])
        value['constraints']=[{'kind':'allergen_exclusion','value':'우유','source_text':'우유 알레르기'}]
        result=semantic.validate_response(wire(value),self.context('우유 알레르기 있어요'))
        self.assertEqual(result['status'],'insufficient_data')
        self.assertEqual(result['recommendations'],[])

    def test_replay_matches_historical_hashes_without_calling_model(self):
        from app.evaluation.replay_semantic_v2 import replay
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(previous,'openai_transport',side_effect=AssertionError('No API')):
            report=replay(folder)
        self.assertEqual(report['model_calls'],0)
        self.assertFalse(report['new_model_quality_measured'])
        self.assertEqual(sum(row['v1']['state']=='accepted' for row in report['cases']),2)
        self.assertEqual(sum(row['v2']['state']=='accepted' for row in report['cases']),3)
