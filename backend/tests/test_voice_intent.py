import asyncio
import unittest
from unittest.mock import patch

from app.main import app
from app.services.llm_direct import DirectError
from app.services.voice.audio import PreparedVoiceAudio
from test_voice_audio import post_audio, MIME_TYPE
from test_voice_options import menu


class VoiceIntentTests(unittest.TestCase):
    def post(self, text, intent=None, *, stage='menu', extra=(), failure=None, rows=None):
        fields = [('stage', stage), *extra]
        if intent is not None:
            fields.append(('intent', intent))
        result = {'result': {'status': 'recommend', 'recommendations': [
            {'menu_id': 'cafe_latte', 'temperature': 'COLD', 'reason': 'fixture'}],
            'questions': [], 'missing_information': []}}
        with patch('app.routers.voice.list_menus', return_value=rows or [menu()]), \
             patch('app.routers.voice._prepare_upload', return_value=(PreparedVoiceAudio(b'\0\0', 16000, 1), 2)), \
             patch('app.routers.voice.transcribe_voice', return_value=text) as stt, \
             patch('app.routers.voice.llm_recommend', return_value=result, side_effect=failure) as llm:
            status, body = asyncio.run(post_audio(b'fixture', 'sample.webm', MIME_TYPE,
                path='/api/voice/interpret', fields=fields))
            return status, body, stt.call_count, llm.call_count

    def test_exact_menu_routes_by_intent_and_recommendation_keeps_pending_options(self):
        for intent, expected, calls in [('order', 'select_menu', 0), ('recommend', 'direct_recommendation', 1),
                                         (None, 'select_menu', 0)]:
            with self.subTest(intent=intent):
                status, body, _, count = self.post('아이스 카페라떼 샷 추가 포장', intent)
                self.assertEqual((status, body['action']['type'], count), (200, expected, calls))
                options = body['recognized_options']
                self.assertEqual((options['temperature'], options['service_type']), ('COLD', 'TAKEOUT'))
                self.assertEqual(options['customization']['status'], 'pending' if intent == 'recommend' else 'resolved')
                if intent == 'recommend': self.assertEqual(options['customization']['option_ids'], [])

    def test_unknown_order_never_calls_llm_but_legacy_and_recommend_do(self):
        for intent in ('order', 'recommend', None):
            status, body, _, count = self.post('시원한 음료 추천해 주세요', intent)
            self.assertEqual(status, 200)
            self.assertEqual(count, 0 if intent == 'order' else 1)
            self.assertEqual(body['action']['type'], 'retry' if intent == 'order' else 'direct_recommendation')
            self.assertEqual(body['recognized_options']['temperature'], 'COLD')

    def test_empty_transcript_never_calls_llm(self):
        for text in ('', '  ', '...'):
            for intent in ('order', 'recommend', None):
                with self.subTest(text=text, intent=intent):
                    status, body, _, count = self.post(text, intent)
                    self.assertEqual((status, count), (200, 0))
                    self.assertEqual(body['action'], {'type': 'retry', 'reason': 'EMPTY_TRANSCRIPT'})

    def test_restart_precedes_both_intents(self):
        for intent in ('order', 'recommend', None):
            for stage, extra in [('menu', ()), ('recommendations', [('candidate_menu_ids', 'cafe_latte')])]:
                status, body, _, count = self.post('다시 추천', intent, stage=stage, extra=extra)
                self.assertEqual((status, body['action']['type'], count), (200, 'restart_recommendation', 0))
                self.assertNotIn('recognized_options', body)

    def test_order_candidate_selection_and_outside_candidate_rejection(self):
        rows = [menu(), {**menu(), 'menu_id': 'tea', 'name': '레몬티'}]
        for text, expected in [('첫 번째', 'select_menu'), ('레몬티', 'retry')]:
            status, body, _, count = self.post(text, 'order', stage='recommendations',
                extra=[('candidate_menu_ids', 'cafe_latte')], rows=rows)
            self.assertEqual((status, body['action']['type'], count), (200, expected, 0))
            if expected == 'retry': self.assertEqual(body['action']['reason'], 'OUTSIDE_CANDIDATES')
        status, body, _, count = self.post('첫 번째', 'recommend', stage='recommendations',
            extra=[('candidate_menu_ids', 'cafe_latte')])
        self.assertEqual((status, body['action']['type'], count), (200, 'direct_recommendation', 1))

    def test_order_retains_unavailable_validation(self):
        status, body, _, count = self.post('카페라떼', 'order', rows=[{**menu(), 'is_available': False}])
        self.assertEqual((status, count), (200, 0))
        self.assertEqual(body['action'], {'type': 'retry', 'reason': 'MENU_UNAVAILABLE'})

    def test_named_order_does_not_require_registered_options(self):
        americano = {**menu(), 'menu_id': 'iced_americano', 'name': '아메리카노'}
        vanilla = {**menu(), 'menu_id': 'vanilla_americano', 'name': '바닐라 아메리카노'}
        rows = [americano, vanilla, menu()]
        for text, menu_id in [
            ('뜨듯한 아메리카노 부탁드립니다', 'iced_americano'),
            ('뜨듯한 바닐라 아메리카노', 'vanilla_americano'),
            ('아메리카노 말고 라떼', 'cafe_latte'),
        ]:
            with self.subTest(text=text):
                status, body, _, calls = self.post(text, 'order', rows=rows)
                self.assertEqual((status, body['action'], calls),
                                 (200, {'type': 'select_menu', 'menu_id': menu_id}, 0))
                self.assertNotIn('recognized_options', body)
        _, body, _, _ = self.post('아메리카노나 라떼', 'order', rows=rows)
        self.assertEqual(body['action'], {'type': 'retry', 'reason': 'UNRECOGNIZED'})
        _, body, _, _ = self.post('뜨듯한 바닐라 아메리카노', 'order',
                                  rows=[americano, {**vanilla, 'is_available': False}])
        self.assertEqual(body['action'], {'type': 'retry', 'reason': 'MENU_UNAVAILABLE'})

    def test_named_cart_from_recommendations_keeps_candidate_boundary(self):
        rows = [menu(), {**menu(), 'menu_id': 'tea', 'name': '레몬티'}]
        extra = [('candidate_menu_ids', 'cafe_latte')]
        _, body, _, _ = self.post('뜨듯한 카페라떼 두 잔', 'order',
                                  stage='recommendations', extra=extra, rows=rows)
        self.assertEqual(body['action']['type'], 'select_items')
        self.assertEqual(body['action']['items'][0]['quantity'], 2)
        _, body, _, _ = self.post('카페라떼 두 잔이랑 레몬티', 'order',
                                  stage='recommendations', extra=extra, rows=rows)
        self.assertEqual(body['action'], {'type': 'retry', 'reason': 'OUTSIDE_CANDIDATES'})

    def test_invalid_intent_or_stage_rejected_before_transcription(self):
        cases = [('unknown', 'menu', ()),
                 ('order', 'temperature', [('selected_menu_id', 'cafe_latte')]),
                 ('recommend', 'service_type', [('selected_menu_id', 'cafe_latte')]),
                 ('order', 'customization', [('selected_menu_id', 'cafe_latte'), ('selected_temperature', 'COLD')]),
                 ('recommend', 'menu_confirmation', ()), ('order', 'review', ())]
        for intent, stage, extra in cases:
            with self.subTest(intent=intent, stage=stage):
                status, body, stt, llm = self.post('카페라떼', intent, stage=stage, extra=extra)
                self.assertEqual((status, stt, llm), (422, 0, 0))
                if intent == 'unknown': self.assertIsInstance(body['detail'], list)
                else: self.assertEqual(body['detail']['code'], 'INVALID_VOICE_CONTEXT')

    def test_recommendation_failure_has_no_order_fallback(self):
        status, body, _, count = self.post('카페라떼', 'recommend', failure=DirectError('fixture'))
        self.assertEqual((status, count), (502, 1))
        self.assertEqual(body['detail']['code'], 'LLM_RECOMMENDATION_FAILED')
        self.assertNotIn('action', body)

    def test_recommendation_does_not_invent_user_temperature(self):
        _, body, _, _ = self.post('카페라떼', 'recommend')
        self.assertNotIn('recognized_options', body)
        status, body, _, count = self.post('따뜻한 카페라떼', 'recommend')
        self.assertEqual((status, count), (502, 1))
        self.assertEqual(body['detail']['code'], 'LLM_RECOMMENDATION_FAILED')

    def test_openapi_exposes_optional_enum(self):
        schema = app.openapi()
        ref = schema['paths']['/api/voice/interpret']['post']['requestBody']['content']['multipart/form-data']['schema']['$ref']
        form = schema['components']['schemas'][ref.split('/')[-1]]
        self.assertNotIn('intent', form['required'])
        self.assertIn({'type': 'string', 'enum': ['order', 'recommend']}, form['properties']['intent']['anyOf'])
