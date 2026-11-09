import asyncio
import json
import os
import unittest
from unittest.mock import patch

from app.main import app
from app.routers import recommendation_text as route
from app.services.llm_direct import DirectError
from test_llm_direct_v3 import candidate, envelope
from app.experiments.run_easy_v3 import ROOT


async def request(body=None, method='POST'):
    messages = []
    async def receive():
        return {'type': 'http.request', 'body': json.dumps(body or {}).encode(), 'more_body': False}
    async def send(message):
        messages.append(message)
    path = '/api/experiments/recommend-text'
    await app({'type': 'http', 'asgi': {'version': '3.0'}, 'http_version': '1.1', 'method': method,
               'scheme': 'http', 'path': path, 'raw_path': path.encode(), 'query_string': b'',
               'root_path': '', 'headers': [(b'content-type', b'application/json')],
               'server': ('testserver', 80), 'client': ('127.0.0.1', 12345)}, receive, send)
    status = next(m['status'] for m in messages if m['type'] == 'http.response.start')
    return status, json.loads(b''.join(m.get('body', b'') for m in messages if m['type'] == 'http.response.body'))


class RecommendationTextTests(unittest.TestCase):
    def setUp(self):
        self.menus = json.loads((ROOT/'docs/experiments/2026-11-09-first-live/results.json').read_text(encoding='utf-8'))['smoke']['catalog']
        self.environment = patch.dict(os.environ, {'LLM_TEXT_EXPERIMENT_ENABLED': '0', 'OPENAI_API_KEY': ''})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.catalog = patch.object(route, 'list_menus', return_value=self.menus)
        self.catalog.start()
        self.addCleanup(self.catalog.stop)
        self.network = patch('urllib.request.urlopen', side_effect=AssertionError('No real network in tests'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def enable(self):
        os.environ['LLM_TEXT_EXPERIMENT_ENABLED'] = '1'
        os.environ['OPENAI_API_KEY'] = 'unit-test-placeholder'
        os.environ['LLM_TEXT_MODEL'] = route.DEFAULT_MODEL

    def live_body(self, text='레몬 산미와 탄산이 있는 음료를 3500원 이하로 추천해 주세요.'):
        return {'transcript': text, 'engine': 'llm-v3', 'paid_call_confirmed': True}

    def test_default_is_existing_and_no_api_call(self):
        with patch.object(route, 'existing_recommend', return_value=['lemonade']) as legacy, patch.object(route, 'openai_transport') as llm:
            status, result = asyncio.run(request({'transcript': '추천해 주세요'}))
        self.assertEqual(status, 200)
        legacy.assert_called_once()
        llm.assert_not_called()
        self.assertEqual(result['engine'], 'existing')
        self.assertEqual(result['api_calls'], 0)

    def test_flag_confirmation_and_key_are_required(self):
        self.assertEqual(asyncio.run(request(self.live_body()))[0], 403)
        os.environ['LLM_TEXT_EXPERIMENT_ENABLED'] = '1'
        body = self.live_body()
        body['paid_call_confirmed'] = False
        self.assertEqual(asyncio.run(request(body))[0], 422)
        self.assertEqual(asyncio.run(request(self.live_body()))[0], 503)

    def test_actual_v3_path_with_mocked_provider_once(self):
        self.enable()
        with patch.object(route, 'openai_transport', return_value=envelope(candidate('lemonade', fields=['description']))) as llm:
            status, result = asyncio.run(request(self.live_body()))
        self.assertEqual(status, 200)
        self.assertEqual(llm.call_count, 1)
        self.assertEqual(llm.call_args.args[0]['reasoning'], {'effort': 'none'})
        self.assertEqual(result['api_calls'], 1)
        self.assertEqual(result['result']['recommendations'][0]['name'], '레몬에이드')
        self.assertIn('확인된 설명', result['result']['recommendations'][0]['reason'])
        self.assertNotIn('unit-test-placeholder', json.dumps(result))

    def test_budget_rejection_no_fallback_and_no_retry(self):
        self.enable()
        with patch.object(route, 'openai_transport', return_value=envelope(candidate('lemonade'))) as llm, patch.object(route, 'existing_recommend') as legacy:
            status, result = asyncio.run(request(self.live_body('3000원 이하로 추천해 주세요')))
        self.assertEqual(status, 502)
        self.assertEqual(result['detail']['code'], 'INELIGIBLE_OPTION')
        self.assertEqual(llm.call_count, 1)
        legacy.assert_not_called()

    def test_clarification_and_missing_data_are_preserved(self):
        self.enable()
        for action in ('clarify', 'insufficient_data'):
            value = {'status': action, 'requested_menu_name': '', 'recommendations': [],
                     'questions': ['카페인 기준을 알려주세요.'] if action == 'clarify' else [],
                     'missing_information': ['성분 자료가 필요해요.'] if action == 'insufficient_data' else [],
                     'unresolved_requirements': ['확인 필요']}
            with self.subTest(action=action), patch.object(route, 'openai_transport', return_value=envelope(value)):
                status, result = asyncio.run(request(self.live_body()))
                self.assertEqual(status, 200)
                self.assertEqual(result['result']['status'], action)

    def test_concurrent_llm_request_is_blocked(self):
        self.enable()
        route.llm_slot.acquire()
        try:
            with patch.object(route, 'openai_transport') as llm:
                status, result = asyncio.run(request(self.live_body()))
                self.assertEqual(status, 503)
                self.assertEqual(result['detail']['code'], 'LLM_TEXT_BUSY')
                llm.assert_not_called()
        finally:
            route.llm_slot.release()

    def test_whitespace_oversized_and_extra_fields_rejected(self):
        for value in ({'transcript': '   '}, {'transcript': 'x'*4001},
                      {'transcript': '추천', 'api_key': 'never-send-keys'}):
            with self.subTest(value=list(value)), patch.object(route, 'openai_transport') as llm:
                self.assertEqual(asyncio.run(request(value))[0], 422)
                llm.assert_not_called()

    def test_config_does_not_expose_key_and_voice_remains_existing(self):
        self.enable()
        status, result = asyncio.run(request(method='GET'))
        self.assertEqual(status, 200)
        self.assertEqual(result['voice_engine'], 'existing')
        self.assertTrue(result['api_key_configured'])
        self.assertNotIn('unit-test-placeholder', json.dumps(result))

    def test_provider_error_returns_safe_code_without_retry(self):
        self.enable()
        with patch.object(route, 'openai_transport', side_effect=DirectError('PROVIDER_HTTP_429')) as llm:
            status, result = asyncio.run(request(self.live_body()))
        self.assertEqual(status, 502)
        self.assertEqual(result['detail']['code'], 'PROVIDER_HTTP_429')
        self.assertEqual(llm.call_count, 1)
