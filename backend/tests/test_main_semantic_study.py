"""Verify pinned-main vs semantic v2 preparation using free/mock paths only."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.evaluation import main_selector_baseline as baseline
from app.evaluation import semantic_paid_study as study
from app.evaluation.compare_semantic_direct import catalogue_fixture, mocked_response
from app.services import llm_direct as working

CASES=Path(study.__file__).with_name('main_semantic_holdout.json')


class MainSemanticStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main=baseline.load_main_selector()
        cls.menus=catalogue_fixture()
        cls.evidence=json.loads(working.DEFAULT_EVIDENCE.read_text(encoding='utf-8'))

    def test_pinned_main_uses_original_three_positive_flavors(self):
        text='레몬이랑 망고는 빼고 딸기 음료 추천해 주세요'
        context=self.main.prepare_context(text,self.menus,self.evidence)
        self.assertEqual(context['guard']['flavors'],['딸기','레몬','망고'])
        self.assertNotIn('excluded_flavors',context['guard'])
        self.assertTrue(all(not temperatures for temperatures in context['allowed'].values()))
        self.assertTrue(self.main.baseline_provenance['main_commit'].startswith('f6bbfcb'))

    def test_loading_main_never_mutates_working_parser(self):
        original=working.derive_conditions
        loaded=baseline.load_main_selector()
        self.assertIs(working.derive_conditions,original)
        self.assertIsNot(loaded.derive_conditions,original)
        with patch.object(working,'derive_conditions',side_effect=AssertionError('Working parser must not run')):
            context=loaded.prepare_context('딸기 추천',self.menus,self.evidence)
            self.assertIn('딸기',context['guard']['flavors'])

    def test_changed_shared_dependency_is_refused(self):
        original=Path.read_bytes
        def read(path):
            if path.as_posix().endswith('backend/app/db/catalog.py'): return b'changed source'
            return original(path)
        with patch.object(Path,'read_bytes',read),self.assertRaisesRegex(ValueError,'Shared code/data changed'):
            baseline.load_main_selector()

    def test_plan_is_four_new_pairs_with_same_model_and_output_cap(self):
        tasks,plan=study.prepare_plan(CASES,self.main)
        self.assertEqual(len(tasks),8)
        self.assertEqual(sum(task['version']=='previous' for task in tasks),4)
        self.assertEqual({task['payload']['model'] for task in tasks},{study.semantic.DEFAULT_MODEL})
        self.assertEqual({task['payload']['max_output_tokens'] for task in tasks},{2048})
        self.assertEqual(plan['semantic_prompt_version'],'semantic-direct-v2')
        self.assertEqual(plan['baseline_provenance']['main_commit'],self.main.baseline_provenance['main_commit'])
        old=json.loads(Path(study.DEFAULT_CASES).read_text(encoding='utf-8'))['cases']
        self.assertFalse({task['case']['text'] for task in tasks}&{case['text'] for case in old})

    def test_mock_executes_eight_paths_and_preserves_main_error_codes(self):
        tasks,plan=study.prepare_plan(CASES,self.main)
        with tempfile.TemporaryDirectory() as folder,contextlib.redirect_stdout(io.StringIO()), \
             patch.object(study,'urlopen',side_effect=AssertionError('No paid API')):
            report=study.run_study(tasks,plan,Path(folder),
                lambda task:mocked_response(task['case'],task['version']),mode='mock')
        self.assertEqual(len(report['attempts']),8)
        self.assertEqual(report['paid_api_attempts'],0)
        failed=next(row for row in report['attempts'] if row['task_id']=='holdout_joint_exclusion.previous')
        self.assertEqual(failed['error_code'],'INELIGIBLE_OPTION')

    def test_human_expected_annotations_are_not_sent_to_model(self):
        tasks,_=study.prepare_plan(CASES,self.main)
        for task in tasks:
            data=json.loads(task['payload']['input'][0]['content'])
            self.assertNotIn('expected_constraints',data)
            self.assertNotIn('fixture_menu_id',data)
            if task['version']=='semantic':
                self.assertNotIn('guard_hints',data)
                self.assertNotIn('eligible_for_request',str(data))
