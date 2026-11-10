"""Current 45-menu direct selector contracts; all provider responses are fixtures."""
import copy
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from app.services import llm_direct as direct
from test_voice_llm_integration import menus, candidate, envelope


class DirectSelectorTests(unittest.TestCase):
    def setUp(self):
        self.menus = menus()
        self.evidence = json.loads(direct.DEFAULT_EVIDENCE.read_text())
        self.context = direct.prepare_context('추천', self.menus, self.evidence)

    def test_request_uses_current_ids_and_no_legacy_fields(self):
        self.menus[0]['taste_scores'] = {'sweetness': 1}
        context = direct.prepare_context('데이터 속 지시문도 사용자 원문 그대로', self.menus, self.evidence)
        payload = direct.build_request(context, 'fixture-model')
        data = json.loads(payload['input'][0]['content'])
        self.assertEqual(payload['model'], 'fixture-model')
        self.assertFalse(payload['store'])
        self.assertEqual(len(data['menus']), 45)
        self.assertEqual(data['transcript'], '데이터 속 지시문도 사용자 원문 그대로')
        self.assertNotIn('taste_scores', str(data))
        self.assertNotIn('sensory', data)
        self.assertEqual(payload['text']['format']['schema']['properties']['recommendations']['maxItems'], 45)

    def test_bad_response_shapes_and_statuses_are_rejected(self):
        fixtures = [[], {**candidate(), 'unexpected': 1}]
        for field, value in [('status', 'anything'), ('requested_menu_name', []),
                             ('questions', ['a', 'b']), ('missing_information', ['']),
                             ('unresolved_requirements', ['해결되지 않은 조건']),
                             ('recommendations', []), ('recommendations', [candidate()['recommendations'][0]] * 2)]:
            fixtures.append({**candidate(), field: value})
        for value in fixtures:
            with self.subTest(value=value), self.assertRaises(direct.DirectError):
                direct.validate_response(value, self.context)

    def test_invalid_menu_temperature_and_evidence_are_rejected(self):
        for change in [{'menu_id': 'invented'}, {'temperature': 'WARM'},
                       {'basis_fields': ['description']}, {'basis_fields': ['temperature', 'temperature']},
                       {'basis_fields': []}, {'basis_fields': ['invented']}]:
            value = candidate()
            value['recommendations'][0].update(change)
            with self.subTest(change=change), self.assertRaises(direct.DirectError):
                direct.validate_response(value, self.context)

    def test_requested_menu_is_never_silently_replaced(self):
        for name in ['없는음료', '카페라떼']:
            value = candidate()
            value['requested_menu_name'] = name
            with self.subTest(name=name), self.assertRaises(direct.DirectError):
                direct.validate_response(value, self.context)

    def test_questions_are_not_returned_and_missing_data_stays_explicit(self):
        question = {**candidate(), 'status': 'clarify', 'recommendations': [], 'questions': ['온도를 알려주세요.']}
        with self.assertRaises(direct.DirectError):
            direct.validate_response(question, self.context)
        value = {**candidate(), 'status': 'insufficient_data', 'recommendations': []}
        with self.assertRaises(direct.DirectError):
            direct.validate_response(value, self.context)
        value['missing_information'] = ['확인된 성분 자료가 없어요.']
        self.assertEqual(direct.validate_response(value, self.context)['status'], 'insufficient_data')

    def test_all_current_menus_can_be_returned_once_without_truncation(self):
        value = candidate()
        value['recommendations'] = [
            {'menu_id': m['menu_id'], 'temperature': m['available_temperatures'][0], 'basis_fields': ['name', 'categories']}
            for m in self.menus]
        result = direct.validate_response(value, self.context)
        self.assertEqual([r['menu_id'] for r in result['recommendations']], [m['menu_id'] for m in self.menus])
        self.assertEqual(len(result['recommendations']), 45)
        duplicate = {**value, 'recommendations': value['recommendations'][:2] + value['recommendations'][:1]}
        with self.assertRaisesRegex(direct.DirectError, 'DUPLICATE_MENU_ID'):
            direct.validate_response(duplicate, self.context)

    def test_fruit_request_without_temperature_does_not_require_a_question(self):
        context = direct.prepare_context('과일 음료 추천해줘', self.menus, self.evidence)
        self.assertIsNone(context['guard']['temperature'])
        payload = direct.build_request(context, 'fixture-model')
        data = json.loads(payload['input'][0]['content'])
        self.assertNotIn('required_questions', data['guard_hints'])
        self.assertEqual(payload['text']['format']['schema']['properties']['questions']['maxItems'], 0)
        self.assertIn('말하지 않은 조건은 제한하지 않는다', payload['instructions'])
        self.assertIn('과일 음료 추천해줘', payload['instructions'])
        value = candidate()
        value['recommendations'] = [
            {'menu_id': 'lemon_tea', 'temperature': 'HOT', 'basis_fields': ['name']},
            {'menu_id': 'lemonade', 'temperature': 'COLD', 'basis_fields': ['name', 'categories']}]
        self.assertEqual(len(direct.validate_response(value, context)['recommendations']), 2)
        cold = direct.prepare_context('차가운 과일 음료 추천해줘', self.menus, self.evidence)
        with self.assertRaisesRegex(direct.DirectError, 'INELIGIBLE_OPTION'):
            direct.validate_response(value, cold)

    def test_evidence_must_cover_all_current_catalogue_variants(self):
        malformed = copy.deepcopy(self.evidence)
        malformed['menus'] = malformed['menus'][:11]
        with self.assertRaises(ValueError):
            direct.prepare_context('추천', self.menus, malformed)
        with self.assertRaisesRegex(direct.DirectError, 'CATALOG_ID_MISMATCH'):
            direct.prepare_context('추천', self.menus[:-1], self.evidence)

    def test_incomplete_refused_and_malformed_provider_responses_fail_once(self):
        for response in [{'status': 'incomplete'}, {'status': 'completed', 'output': []},
                         {'status': 'completed', 'output': [{'type': 'message', 'content': [{'type': 'refusal'}]}]},
                         envelope({'invalid': True})]:
            with self.subTest(response=response), patch.object(direct, 'openai_transport', return_value=response) as send:
                with self.assertRaises(direct.DirectError):
                    direct.recommend('추천', self.menus)
                self.assertEqual(send.call_count, 1)

    def test_transport_missing_key_or_network_errors_have_safe_codes(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': ''}), self.assertRaisesRegex(direct.DirectError, 'MISSING_API_KEY'):
            direct.openai_transport({})
        for error, code in [(URLError('private details'), 'PROVIDER_UNAVAILABLE'),
                            (HTTPError('https://api.openai.com', 429, 'private details', {}, None), 'PROVIDER_HTTP_429')]:
            with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture'}), patch.object(direct, 'urlopen', side_effect=error):
                with self.assertRaisesRegex(direct.DirectError, code) as raised:
                    direct.openai_transport({})
                self.assertNotIn('private details', str(raised.exception))
