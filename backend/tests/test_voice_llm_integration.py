import asyncio
import json
import os
import unittest
from unittest.mock import patch

from app.db.catalog import load_catalog
from app.services import llm_direct as direct
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
        evidence = json.loads(direct.DEFAULT_EVIDENCE.read_text())
        evidence['menus'][0]['variants']['COLD']['description'] = {
            'status': 'unknown', 'value': None, 'source': None, 'checked_date': None, 'note': 'Test-only unknown recipe'}
        with self.assertRaisesRegex(DirectError, 'EVIDENCE_SCOPE_MISMATCH'):
            direct.recommend('추천', self.rows, evidence=evidence, transport=lambda _: envelope(candidate(fields=['description'])))
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

    def test_default_path_uses_llm_and_original_transcript_once(self):
        # An obsolete local setting must not silently select the removed ranker.
        os.environ['RECOMMENDATION_ENGINE'] = 'existing'
        with patch.object(direct, 'openai_transport', return_value=envelope(candidate())) as provider:
            status, value = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(value['action']['type'], 'direct_recommendation')
        self.assertEqual(value['action']['engine'], 'llm-direct')
        self.assertEqual(value['action']['recommendations'][0]['menu_id'], 'iced_americano')
        self.assertEqual(provider.call_count, 1)
        data = json.loads(provider.call_args.args[0]['input'][0]['content'])
        self.assertEqual(data['transcript'], '4000원 이하 음료 추천해 주세요')

    def test_missing_data_action_without_questions(self):
        result = candidate()
        result.update(status='insufficient_data', recommendations=[], missing_information=['성분 자료가 없어요.'])
        with patch.object(direct, 'openai_transport', return_value=envelope(result)):
            status, value = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(value['action']['status'], 'insufficient_data')
        self.assertEqual(value['action']['questions'], [])

    def test_recommendations_are_capped_at_six_and_sixth_candidate_can_be_selected(self):
        rows = menus()
        result = candidate()
        result['recommendations'] = [{'menu_id': m['menu_id'], 'temperature': m['available_temperatures'][0],
                                     'basis_fields': ['name', 'categories']} for m in rows]
        with patch.object(voice, 'transcribe_voice', return_value='음료 추천'), \
                patch.object(direct, 'openai_transport', return_value=envelope(result)):
            status, value = self.post()
        self.assertEqual(status, 200)
        self.assertEqual(len(value['action']['recommendations']), 6)
        fields = [('stage', 'recommendations')] + [('candidate_menu_ids', m['menu_id']) for m in rows[:6]]
        with patch.object(voice, 'transcribe_voice', return_value='6번 주세요'):
            status, value = asyncio.run(post_audio(b'fixture', 'sample.webm', MIME_TYPE,
                                                  path='/api/voice/interpret', fields=fields))
        self.assertEqual(status, 200)
        self.assertEqual(value['action'], {'type': 'select_menu', 'menu_id': rows[5]['menu_id']})

    def test_failure_no_legacy_fallback_or_retry(self):
        os.environ['RECOMMENDATION_ENGINE'] = 'llm-direct'
        with patch.object(direct,'openai_transport',side_effect=DirectError('PROVIDER_HTTP_429')) as provider:
            status,value = self.post()
        self.assertEqual(status,502)
        self.assertEqual(value['detail']['code'],'LLM_RECOMMENDATION_FAILED')
        self.assertEqual(provider.call_count,1)

    def test_named_menu_selection_does_not_call_llm(self):
        os.environ['RECOMMENDATION_ENGINE'] = 'llm-direct'
        with patch.object(voice,'transcribe_voice',return_value='카페라떼 주세요'), patch.object(voice,'llm_recommend') as llm:
            status,value=self.post()
        self.assertEqual(status,200)
        self.assertEqual(value['action']['type'],'select_menu')
        llm.assert_not_called()


if __name__ == '__main__': unittest.main()
