import asyncio
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from app.db.catalog import ROOT, load_option_profiles
from app.schemas.voice import VoiceInterpretResponse
from app.services.voice.interpretation import interpret_transcript
from app.services.voice.options import extract_options
from app.services.voice.audio import PreparedVoiceAudio
from test_voice_audio import post_audio, MIME_TYPE


def menu():
    groups = load_option_profiles(Path(os.environ.get('COMMON_DIR', ROOT / 'common')))['coffee_latte']
    return {'menu_id': 'cafe_latte', 'name': '카페라떼', 'is_available': True,
            'available_temperatures': ['HOT', 'COLD'],
            'variants': [{'temperature': t, 'option_groups': groups} for t in ['HOT', 'COLD']]}


class OptionExtractionTests(unittest.TestCase):
    def test_temperature_and_service_synonyms(self):
        for text, temp, service in [('시원한 음료 포장', 'COLD', 'TAKEOUT'),
                                    ('따뜻한 음료 매장에서', 'HOT', 'DINE_IN'),
                                    ('핫 말고 아이스로 가져갈게요', 'COLD', 'TAKEOUT')]:
            with self.subTest(text=text):
                value = extract_options(text)
                self.assertEqual((value.temperature, value.service_type), (temp, service))

    def test_ambiguity_and_negation_do_not_select(self):
        for text in ['핫이나 아이스', '안 시원한 것', '아이스 말고', '핫 아니고']:
            with self.subTest(text=text):
                value = extract_options(text)
                self.assertIsNone(value.temperature)
                self.assertIn('temperature', value.unresolved_fields)
        value = extract_options('매장 또는 포장')
        self.assertIsNone(value.service_type)
        self.assertIn('service_type', value.unresolved_fields)

    def test_customization_resolves_catalogue_ids(self):
        value = extract_options('아이스 카페라떼 샷 추가하고 바닐라 시럽 추가 포장', menu=menu())
        self.assertEqual(value.customization.status, 'resolved')
        self.assertEqual(value.customization.option_ids, ['shot:extra', 'sweetness:vanilla'])
        self.assertEqual(value.service_type, 'TAKEOUT')

    def test_pending_none_and_omitted_are_distinct(self):
        self.assertIsNone(extract_options('카페라떼 주세요', menu=menu()))
        pending = extract_options('샷 추가', menu=menu()).customization
        self.assertEqual(pending.status, 'pending')
        self.assertEqual(pending.option_ids, [])
        self.assertEqual(pending.intents[0].candidate_option_ids, ['shot:extra'])
        none = extract_options('추가 옵션 없이', menu=menu()).customization
        self.assertEqual((none.status, none.option_ids), ('resolved', []))

    def test_correction_preserves_other_group(self):
        result = extract_options('아이스 샷 추가 말고 연하게 바닐라 시럽 추가', menu=menu())
        self.assertEqual(result.temperature, 'COLD')
        self.assertEqual(result.customization.status, 'resolved')
        self.assertEqual(result.customization.option_ids, ['shot:light', 'sweetness:vanilla'])

    def test_quantities_menu_names_and_temperature_variants(self):
        value = extract_options('두 샷 추가', menu=menu(), temperature='COLD')
        self.assertEqual(value.customization.option_ids, ['shot:double'])
        named = {**menu(), 'name': '휘핑라떼'}
        self.assertIsNone(extract_options('휘핑라떼 주세요', menu=named))
        row = menu()
        row['variants'][1]['option_groups'] = []
        value = extract_options('아이스 샷 추가', menu=row)
        self.assertEqual(value.customization.status, 'needs_clarification')
        self.assertEqual(value.customization.option_ids, [])

    def test_invalid_or_ambiguous_customization(self):
        for text in ['샷 추가 시럽도', '3샷 추가', '세 샷 추가', '샷 추가 샷 추가',
                     '샷 추가 2샷 추가', '샷 추가 없이', '추가 옵션 없이 샷 추가',
                     '샷 추가나 시럽 추가', '샷 추가나 바닐라 시럽 추가', '샷 추가 안 해요', '카라멜 시럽 추가']:
            with self.subTest(text=text):
                custom = extract_options(text, menu=menu(), temperature='COLD').customization
                self.assertEqual(custom.status, 'needs_clarification')
                self.assertTrue(custom.unresolved)
        custom = extract_options('샷 추가 시럽도', menu=menu(), temperature='COLD').customization
        self.assertEqual(custom.option_ids, ['shot:extra'])

    def test_unsupported_temperature(self):
        row = {**menu(), 'available_temperatures': ['HOT']}
        value = extract_options('시원한 카페라떼 샷 추가', menu=row)
        self.assertIsNone(value.temperature)
        self.assertIn('temperature', value.unresolved_fields)
        self.assertNotEqual(value.customization.status, 'resolved')

    def test_compound_actions_and_menu_comparison(self):
        rows = {'cafe_latte': menu(), 'tea': {**menu(), 'menu_id': 'tea', 'name': '레몬티'}}
        self.assertEqual(interpret_transcript('아이스 카페라떼 샷 추가하고 포장해 주세요', 'menu', rows).type, 'select_menu')
        self.assertEqual(interpret_transcript('네 포장이요', 'menu_confirmation', rows).type, 'confirm')
        self.assertEqual(interpret_transcript('네 포장이요', 'review', rows).type, 'retry')
        self.assertEqual(interpret_transcript('레몬티 말고 카페라떼', 'menu', rows).type, 'retry')
        action = interpret_transcript('아이스로 포장', 'temperature', rows, selected_menu_id='cafe_latte')
        self.assertEqual(action.temperature, 'COLD')
        action = interpret_transcript('첫 번째 샷 추가 포장', 'recommendations', rows,
                                      candidate_menu_ids=('cafe_latte',))
        self.assertEqual(action.menu_id, 'cafe_latte')

    def test_old_contract_still_valid(self):
        response = VoiceInterpretResponse.model_validate({'transcript': '', 'action': {'type': 'retry', 'reason': 'EMPTY_TRANSCRIPT'}})
        self.assertNotIn('recognized_options', response.model_dump(exclude_none=True))


class OptionRouteTests(unittest.TestCase):
    def test_confirmation_and_customization_context(self):
        status, body, _ = self.post('네 샷 추가 포장이요', [('stage', 'menu_confirmation'),
            ('selected_menu_id', 'cafe_latte'), ('selected_temperature', 'COLD')])
        self.assertEqual(status, 200)
        self.assertEqual(body['action']['type'], 'confirm')
        self.assertEqual(body['recognized_options']['customization']['status'], 'resolved')
        status, body, _ = self.post('샷 추가 포장', [('stage', 'customization'),
            ('selected_menu_id', 'cafe_latte'), ('selected_temperature', 'COLD')])
        self.assertEqual(status, 200)
        self.assertEqual(body['action'], {'type': 'set_options', 'option_ids': ['shot:extra']})
        self.assertEqual(body['recognized_options']['service_type'], 'TAKEOUT')
        status, _, _ = self.post('샷 추가', [('stage', 'customization'), ('selected_menu_id', 'cafe_latte')])
        self.assertEqual(status, 422)

    def post(self, transcript, fields=None, recommendation=None):
        with patch('app.routers.voice.list_menus', return_value=[menu()]), \
             patch('app.routers.voice._prepare_upload', return_value=(PreparedVoiceAudio(b'\0\0', 16000, 1), 2)), \
             patch('app.routers.voice.transcribe_voice', return_value=transcript), \
             patch('app.routers.voice.llm_recommend', return_value=recommendation) as llm:
            response = asyncio.run(post_audio(b'fixture', 'sample.webm', MIME_TYPE,
                                  path='/api/voice/interpret', fields=fields or [('stage', 'menu')]))
            return *response, llm.call_count

    def test_direct_compound_response_without_llm(self):
        status, body, calls = self.post('아이스 카페라떼 샷 추가하고 포장해 주세요')
        self.assertEqual((status, calls), (200, 0))
        self.assertEqual(body['action'], {'type': 'select_menu', 'menu_id': 'cafe_latte'})
        self.assertEqual(body['recognized_options']['customization']['option_ids'], ['shot:extra'])

    def test_recommendation_keeps_only_spoken_options(self):
        recommendation = {'result': {'status': 'recommend', 'recommendations': [
            {'menu_id': 'cafe_latte', 'temperature': 'COLD', 'reason': 'fixture'}],
            'questions': [], 'missing_information': []}}
        status, body, _ = self.post('시원한 음료 샷 추가해서 추천해 주세요', recommendation=recommendation)
        self.assertEqual(status, 200)
        self.assertEqual(body['recognized_options']['temperature'], 'COLD')
        self.assertEqual(body['recognized_options']['customization']['status'], 'pending')
        status, body, _ = self.post('음료 추천해 주세요', recommendation=recommendation)
        self.assertEqual(status, 200)
        self.assertNotIn('recognized_options', body)
        status, _, _ = self.post('따뜻한 음료 추천해 주세요', recommendation=recommendation)
        self.assertNotEqual(status, 200)

    def test_option_context_and_backward_compatible_response(self):
        status, body, _ = self.post('포장하고 샷 추가', [('stage', 'service_type'),
            ('selected_menu_id', 'cafe_latte'), ('selected_temperature', 'COLD')])
        self.assertEqual(status, 200)
        self.assertEqual(body['recognized_options']['customization']['status'], 'resolved')
        status, body, _ = self.post('카페라떼 주세요')
        self.assertEqual(status, 200)
        self.assertNotIn('recognized_options', body)
        status, _, _ = self.post('카페라떼', [('stage', 'menu'), ('selected_temperature', 'COLD')])
        self.assertEqual(status, 422)
