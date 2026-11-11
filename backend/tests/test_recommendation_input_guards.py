"""Regression tests for explicit flavor exclusions and malformed price input."""
import json
import asyncio
import unittest
from unittest.mock import patch

from app.db.catalog import load_catalog
from app.services import llm_direct as direct
from app.services.recommendation_conditions import derive_conditions


class RecommendationInputGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Real catalogue metadata; availability is synthetic, not the user's DB.
        cls.menus = [{'menu_id': m.menu_id, 'name': m.name, 'price_krw': m.price_krw,
                      'is_available': True, 'categories': list(m.categories),
                      'available_temperatures': [t for t, _ in m.variants]} for m in load_catalog()]
        cls.evidence = json.loads(direct.DEFAULT_EVIDENCE.read_text(encoding='utf-8'))

    def test_excluded_lemon_is_not_a_positive_flavor(self):
        guard = derive_conditions('레몬 말고 딸기 음료 추천해 주세요')
        self.assertEqual(guard['flavors'], ['딸기'])
        self.assertEqual(guard['excluded_flavors'], ['레몬'])
        context = direct.prepare_context('레몬 말고 딸기 음료 추천해 주세요', self.menus, self.evidence)
        self.assertTrue(context['allowed']['strawberry_latte'])
        self.assertEqual(context['allowed']['lemonade'], [])

    def test_excluded_flavor_is_enforced_even_if_the_model_selects_it(self):
        context = direct.prepare_context('레몬은 빼고 음료 추천해 주세요', self.menus, self.evidence)
        value = {'status': 'recommend', 'requested_menu_name': '', 'recommendations': [
            {'menu_id': 'lemonade', 'temperature': 'COLD', 'basis_fields': ['description']}],
            'questions': [], 'missing_information': [], 'unresolved_requirements': []}
        with self.assertRaisesRegex(direct.DirectError, 'INELIGIBLE_OPTION'):
            direct.validate_response(value, context)

    def test_flavor_exclusion_does_not_claim_ingredient_or_allergy_absence(self):
        guard = derive_conditions('레몬 맛은 싫어요. 딸기로 추천해 주세요')
        self.assertEqual(guard['excluded_flavors'], ['레몬'])
        self.assertFalse(guard['milk_free'])
        allergy = derive_conditions('레몬 알레르기라 레몬 빼주세요')
        self.assertTrue(allergy['unsupported_conditions'])

    def test_do_not_exclude_and_latest_explicit_flavor_mention(self):
        self.assertNotIn('레몬', derive_conditions('레몬은 빼지 마세요')['excluded_flavors'])
        guard = derive_conditions('레몬 말고, 아니 레몬으로 추천해 주세요')
        self.assertIn('레몬', guard['flavors'])
        self.assertNotIn('레몬', guard['excluded_flavors'])

    def test_invalid_amount_does_not_escape_as_catalogue_error(self):
        for text in ('3,00원 이하 추천', '일만오천원 이하 추천', '1000원에서 3,00원 사이',
                     '-3000원 이하 추천', '1000원에서 -4000원 사이'):
            with self.subTest(text=text):
                context = direct.prepare_context(text, self.menus, self.evidence)
                self.assertTrue(context['guard']['unsupported_conditions'])
                value = {'status': 'insufficient_data', 'requested_menu_name': '', 'recommendations': [],
                         'questions': [], 'missing_information': ['가격 조건을 확인할 수 없어요.'],
                         'unresolved_requirements': []}
                self.assertEqual(direct.validate_response(value, context)['status'], 'insufficient_data')

    def test_invalid_price_never_silently_allows_a_recommendation(self):
        context = direct.prepare_context('3,00원 이하 추천', self.menus, self.evidence)
        value = {'status': 'recommend', 'requested_menu_name': '', 'recommendations': [
            {'menu_id': 'iced_americano', 'temperature': 'COLD', 'basis_fields': ['price_krw']}],
            'questions': [], 'missing_information': [], 'unresolved_requirements': []}
        with self.assertRaisesRegex(direct.DirectError, 'UNRESOLVED_HARD_CONDITION'):
            direct.validate_response(value, context)

    def test_valid_money_forms_and_ranges_stay_supported(self):
        for phrase in ('3000원 이하', '3,000원 이하', '삼천 원 이하', '3천 원 이하'):
            with self.subTest(phrase=phrase):
                self.assertEqual(derive_conditions(phrase)['max_price_krw'], 3000)
        guard = derive_conditions('2000원에서 4000원 사이')
        self.assertEqual((guard['min_price_krw'], guard['max_price_krw']), (2000,4000))
        corrected = derive_conditions('3,00원 아니 3천 원 이하로 추천해 주세요')
        self.assertEqual(corrected['max_price_krw'], 3000)
        self.assertEqual(corrected['unsupported_conditions'], [])

    def test_malformed_price_api_returns_data_notice_not_catalogue_503(self):
        from app.services.voice.audio import PreparedVoiceAudio
        from test_voice_audio import post_audio, MIME_TYPE
        value = {'status': 'insufficient_data', 'requested_menu_name': '', 'recommendations': [],
                 'questions': [], 'missing_information': ['가격 조건을 확인할 수 없어요.'],
                 'unresolved_requirements': []}
        reply = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(value)}]}]}
        with patch('app.routers.voice.list_menus', return_value=self.menus), \
             patch('app.routers.voice._prepare_upload', return_value=(PreparedVoiceAudio(b'\0\0', 16000, 1), 2)), \
             patch('app.routers.voice.transcribe_voice', return_value='3,00원 이하 추천'), \
             patch.object(direct, 'openai_transport', return_value=reply) as provider:
            status, response = asyncio.run(post_audio(b'fixture', 'sample.webm', MIME_TYPE,
                path='/api/voice/interpret', fields=[('stage','menu'),('intent','recommend')]))
        self.assertEqual(status, 200)
        self.assertEqual(response['action']['status'], 'insufficient_data')
        self.assertEqual(provider.call_count, 1)


if __name__ == '__main__': unittest.main()
