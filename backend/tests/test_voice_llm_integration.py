import asyncio
import json
import os
import unittest
from unittest.mock import patch

from app.db.catalog import load_catalog
from app.services.voice import llm_recommendation as direct
from app.services.llm_direct import DirectError
from app.services.voice.audio import PreparedVoiceAudio
from app.routers import voice
from test_voice_audio import post_audio, MIME_TYPE


def menus():
    return [{'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
             'is_available': True, 'categories': list(m.categories),
             'available_temperatures': [t for t, _ in m.variants]} for m in load_catalog()]


def candidate(mid='iced_americano', temp='COLD', fields=None):
    return {'status': 'recommend', 'requested_menu_name': '',
            'recommendations': [{'menu_id': mid, 'temperature': temp, 'basis_fields': fields or ['price_krw', 'temperature']}],
            'questions': [], 'missing_information': [], 'unresolved_requirements': []}


def envelope(value):
    return {'status': 'completed', 'model': 'fixture', 'usage': None,
            'output': [{'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(value)}]}]}


class CurrentCatalogueTests(unittest.TestCase):
    def setUp(self):
        self.rows = menus()  # Current identities/prices, SYNTHETIC availability.

    def test_menu_api_contract_accepts_all_45_current_names_and_categories(self):
        from app.schemas.menus import MenusResponse
        rows = []
        for m in load_catalog():
            variants = [{'temperature': t, 'image_url': image, 'option_groups': m.option_groups} for t, image in m.variants]
            rows.append({'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
                         'categories': list(m.categories), 'is_available': True,
                         'display_order': m.display_order, 'is_featured': m.is_featured,
                         'available_temperatures': [v['temperature'] for v in variants],
                         'variants': variants, 'image_url': variants[-1]['image_url']})
        result = MenusResponse(menus=rows)
        self.assertEqual(len(result.menus),45)
        self.assertTrue(all(m.name.strip() for m in result.menus))

    def test_45_menus_without_csv_or_editorial_tags(self):
        calls = []
        def send(payload):
            calls.append(payload)
            return envelope(candidate())
        with patch('app.services.recommendation.load_scores', side_effect=AssertionError('No taste scores')):
            direct.recommend('4000원 이하 차가운 음료', self.rows, transport=send)
        data = json.loads(calls[0]['input'][0]['content'])
        self.assertEqual(len(data['menus']), 45)
        self.assertNotIn('sensory', data)
        self.assertEqual(len(calls), 1)

    def test_current_database_price_is_used(self):
        next(m for m in self.rows if m['menu_id'] == 'iced_americano')['price_krw'] = 1234
        result = direct.recommend('2000원 이하', self.rows, transport=lambda _: envelope(candidate()))
        self.assertIn('1,234원', result['result']['recommendations'][0]['reason'])

    def test_price_and_unavailable_are_rejected(self):
        with self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
            direct.recommend('2000원 이하', self.rows, transport=lambda _: envelope(candidate()))
        self.rows[0]['is_available'] = False
        mid = self.rows[0]['menu_id']
        with self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
            direct.recommend('추천', self.rows, transport=lambda _: envelope(candidate(mid, self.rows[0]['available_temperatures'][0])))

    def test_unknown_recipe_is_not_imported_from_old_menu_name(self):
        with self.assertRaisesRegex(DirectError, 'EVIDENCE_SCOPE_MISMATCH'):
            direct.recommend('추천', self.rows, transport=lambda _: envelope(candidate(fields=['description'])))
        for text in ('우유 빼주세요', '카페인 없는 음료'):
            with self.subTest(text=text), self.assertRaisesRegex(DirectError, 'INELIGIBLE_OPTION'):
                direct.recommend(text, self.rows, transport=lambda _: envelope(candidate()))


class VoiceRouteIntegrationTests(unittest.TestCase):
    def setUp(self):
        for target, replacement in [
            ('app.routers.voice.list_menus', menus()),
            ('app.routers.voice._prepare_upload', (PreparedVoiceAudio(b'\x01\x00'*16000,16000,1), 100)),
            ('app.routers.voice.transcribe_voice', '4000원 이하 음료 추천해 주세요'),
        ]:
            mock = patch(target, return_value=replacement)
            mock.start(); self.addCleanup(mock.stop)
        env = patch.dict(os.environ, {'RECOMMENDATION_ENGINE': 'existing'})
        env.start(); self.addCleanup(env.stop)
        network = patch('app.services.llm_direct.urlopen', side_effect=AssertionError('No paid calls'))
        network.start(); self.addCleanup(network.stop)

    def post(self):
        return asyncio.run(post_audio(b'fixture', 'sample.webm', MIME_TYPE, path='/api/voice/interpret', fields=[('stage','menu')]))

    def test_default_path_remains_existing(self):
        with patch.object(voice, 'recommend', return_value=['iced_americano']) as existing, patch.object(voice, 'llm_recommend') as llm:
            status, value = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(value['action']['type'], 'recommendation_results')
        existing.assert_called_once(); llm.assert_not_called()

    def test_stt_transcript_reaches_v3_in_opt_in_mode(self):
        os.environ['RECOMMENDATION_ENGINE'] = 'llm-direct'
        with patch.object(direct, 'openai_transport', return_value=envelope(candidate())) as provider, patch.object(voice, 'recommend') as existing:
            status, value = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(value['action']['type'], 'direct_recommendation')
        self.assertEqual(value['action']['engine'], 'llm-direct')
        self.assertEqual(value['action']['recommendations'][0]['menu_id'], 'iced_americano')
        self.assertEqual(provider.call_count, 1)
        data = json.loads(provider.call_args.args[0]['input'][0]['content'])
        self.assertEqual(data['transcript'], '4000원 이하 음료 추천해 주세요')
        existing.assert_not_called()

    def test_question_and_missing_data_actions(self):
        os.environ['RECOMMENDATION_ENGINE'] = 'llm-direct'
        for action in ('clarify','insufficient_data'):
            result = candidate()
            result.update(status=action, recommendations=[],
                          questions=['원하는 온도는 무엇인가요?'] if action == 'clarify' else [],
                          missing_information=['성분 자료가 필요해요.'] if action == 'insufficient_data' else [])
            with self.subTest(action=action), patch.object(direct,'openai_transport',return_value=envelope(result)):
                status,value = self.post()
                self.assertEqual(status,200)
                self.assertEqual(value['action']['status'],action)

    def test_failure_no_legacy_fallback_or_retry(self):
        os.environ['RECOMMENDATION_ENGINE'] = 'llm-direct'
        with patch.object(direct,'openai_transport',side_effect=DirectError('PROVIDER_HTTP_429')) as provider, patch.object(voice,'recommend') as existing:
            status,value = self.post()
        self.assertEqual(status,502)
        self.assertEqual(value['detail']['code'],'LLM_RECOMMENDATION_FAILED')
        self.assertEqual(provider.call_count,1); existing.assert_not_called()

    def test_named_menu_selection_does_not_call_llm(self):
        os.environ['RECOMMENDATION_ENGINE'] = 'llm-direct'
        with patch.object(voice,'transcribe_voice',return_value='카페라떼 주세요'), patch.object(voice,'llm_recommend') as llm:
            status,value=self.post()
        self.assertEqual(status,200)
        self.assertEqual(value['action']['type'],'select_menu')
        llm.assert_not_called()


if __name__ == '__main__': unittest.main()
