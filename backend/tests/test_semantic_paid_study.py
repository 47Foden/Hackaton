"""Paid-study machinery tested with fake transports ONLY. Never read the real .env."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from app.evaluation import semantic_paid_study as study
from app.evaluation.compare_semantic_direct import mocked_response


class PaidStudyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.tasks, cls.plan = study.prepare_plan()

    def execute(self, output, client, **kwargs):
        with contextlib.redirect_stdout(io.StringIO()):
            return study.run_study(self.tasks,self.plan,Path(output),client,wait=lambda _:None,**kwargs)

    def fake(self, task):
        value=mocked_response(task['case'],task['version'])
        value['usage']={'input_tokens':100,'output_tokens':50,'input_tokens_details':{'cached_tokens':0}}
        return value

    def test_four_cases_each_version_with_equal_reduced_output_cap(self):
        self.assertEqual(len(self.tasks),8)
        self.assertEqual(sum(task['version']=='previous' for task in self.tasks),4)
        self.assertEqual(sum(task['version']=='semantic' for task in self.tasks),4)
        self.assertEqual({task['payload']['max_output_tokens'] for task in self.tasks},{2048})
        self.assertEqual(self.plan['study_max_output_tokens'],2048)
        self.assertAlmostEqual(self.plan['reference_estimate_usd'],.20)

    def test_mock_is_unmeasured_and_real_transport_never_called(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(study,'urlopen',side_effect=AssertionError('No API')):
            result=self.execute(folder,self.fake,mode='mock')
            self.assertEqual(len(result['attempts']),8)
            self.assertEqual(result['paid_api_attempts'],0)
            self.assertTrue(all(r['candidate_annotation_check'] is None and r['usage'] is None for r in result['attempts']))

    def test_resume_skips_success_and_provider_failure_with_eight_attempt_cap(self):
        calls=[]
        def first(task):
            calls.append(task['id'])
            if len(calls)==3:
                error=study.previous.DirectError('PROVIDER_HTTP_429')
                error.provider_details={'code':'rate_limit_exceeded'}
                raise error
            return self.fake(task)
        def remaining(task): calls.append(task['id']); return self.fake(task)
        with tempfile.TemporaryDirectory() as folder:
            initial=self.execute(folder,first)
            self.assertEqual(len(initial['attempts']),3)
            self.assertIsNone(initial['attempts'][-1]['candidate_annotation_check'])
            resumed=self.execute(folder,remaining)
            self.assertEqual(len(resumed['attempts']),8)
            self.assertEqual(len(calls),len(set(calls)))
            self.execute(folder,lambda _:self.fail('Ninth call'))
            self.assertEqual(resumed['attempts'][2]['state'],'provider_error_unmeasured')

    def test_interrupted_attempt_is_saved_and_never_repeated(self):
        seen=[]
        def interrupted(task): seen.append(task['id']); raise KeyboardInterrupt()
        def remaining(task): seen.append(task['id']); return self.fake(task)
        with tempfile.TemporaryDirectory() as folder:
            initial=self.execute(folder,interrupted)
            self.assertEqual(initial['attempts'][0]['state'],'unknown_after_interruption')
            self.execute(folder,remaining)
            self.assertEqual(len(seen),8)
            self.assertEqual(len(set(seen)),8)

    def test_changed_plan_refuses_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            self.execute(folder,self.fake,mode='mock')
            changed=copy.deepcopy(self.plan); changed['fingerprint']='changed'
            with self.assertRaisesRegex(ValueError,'changed'):
                study.run_study(self.tasks,changed,Path(folder),lambda _:self.fail('No call'),mode='mock')

    def test_error_details_whitelist_never_keeps_message_or_unknown_codes(self):
        body={'error':{'message':'PRIVATE-ERROR-DETAIL','code':'insufficient_quota','type':'insufficient_quota'}}
        error=HTTPError('https://api.openai.com',429,'private',{'Retry-After':'40'},io.BytesIO(json.dumps(body).encode()))
        details=study.safe_http_details(error)
        error.close()
        self.assertEqual(details['retry_after_seconds'],40)
        self.assertEqual(details['code'],'insufficient_quota')
        self.assertNotIn('PRIVATE',str(details))
        error=HTTPError('https://api.openai.com',429,'private',{},io.BytesIO(b'{"error":{"code":"PRIVATE-UNKNOWN"}}'))
        self.assertEqual(study.safe_http_details(error)['code'],'unclassified')
        error.close()

    def test_secret_is_redacted_from_json_and_report(self):
        secret='SYNTHETIC_TEST_SECRET_ONLY'
        def echo(task):
            value=self.fake(task)
            content=json.loads(value['output'][0]['content'][0]['text'])
            if task['version']=='semantic': content['request_summary']=secret
            else: content['requested_menu_name']=secret
            value['output'][0]['content'][0]['text']=json.dumps(content)
            return value
        with tempfile.TemporaryDirectory() as folder:
            self.execute(folder,echo,mode='mock',secret=secret)
            self.assertNotIn(secret,(Path(folder)/'results.json').read_text(encoding='utf-8'))
            self.assertNotIn(secret,(Path(folder)/'report.ko.md').read_text(encoding='utf-8'))

    def test_key_parser_uses_only_fake_file_and_cost_is_usage_based(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'fake.env'
            path.write_text('\ufeffOPENAI_API_KEY="TEST_VALUE_ONLY"\n',encoding='utf-8')
            self.assertEqual(study.load_key(path),'TEST_VALUE_ONLY')
        self.assertAlmostEqual(study.token_cost({'input_tokens':1000000,'output_tokens':1000000,
            'input_tokens_details':{'cached_tokens':100000}}),5.1825)
        self.assertIsNone(study.token_cost(None))
