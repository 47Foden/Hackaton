"""Archive-derived diagnostics; draft labels are not live LLM accuracy ground truth."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.evaluation.speech20 import load_manifest, run, save_report, verify_archive, decode_mp3
from app.services import llm_direct as direct
from app.services.recommendation_conditions import derive_conditions
from test_voice_llm_integration import menus, candidate

ROOT = Path(__file__).resolve().parents[2]


class SpeechArchiveTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest()

    def test_archive_has_twenty_actual_audio_entries_with_checksums(self):
        verify_archive(ROOT / self.manifest['archive'], self.manifest)
        self.assertEqual(len(self.manifest['cases']), 20)
        self.assertFalse(self.manifest['human_verified'])
        # Filename numbering was explicitly rejected by the user; audio-006 is not spreadsheet S006.
        c = next(c for c in self.manifest['cases'] if c['id'] == 'audio-006')
        self.assertIn('프라페', c['reference_text'])
        self.assertTrue(all(c['asr_hypotheses'] for c in self.manifest['cases']))

    def test_prompt_examples_and_prompt_holdout_never_overlap(self):
        examples = direct.load_condition_examples()
        used = {e['source_id'] for e in examples}
        heldout = {c['id'] for c in self.manifest['cases'] if c['split'] == 'prompt_holdout'}
        self.assertEqual(len(used), 12)
        self.assertEqual(len(heldout), 8)
        self.assertFalse(used & heldout)
        payload = direct.build_request(direct.prepare_context('추천', menus(),
            json.loads(direct.DEFAULT_EVIDENCE.read_text())), 'fixture')
        self.assertEqual({e['source_id'] for e in json.loads(payload['input'][0]['content'])['condition_examples']}, used)

    def test_offline_run_covers_twenty_draft_condition_assertions_without_network(self):
        with patch('app.services.llm_direct.urlopen', side_effect=AssertionError('offline network')), \
                patch('app.evaluation.speech20.transcribe_voice', side_effect=AssertionError('offline ASR')):
            report = run(self.manifest)
        self.assertEqual(report['case_count'], 20)
        self.assertEqual(report['guard_case_matches'], 20)
        self.assertEqual(report['api_calls_attempted'], 0)
        self.assertFalse(report['reference_human_verified'])
        self.assertIn('not_measured', report['recommendation_quality'])
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'report'
            save_report(report, path)
            self.assertTrue((path / 'results.csv').exists())
            with self.assertRaises(FileExistsError): save_report(report, path)

    def test_audio_decoder_handles_real_archive_mp3(self):
        import zipfile
        with zipfile.ZipFile(ROOT / self.manifest['archive']) as z:
            pcm = decode_mp3(z.read(self.manifest['cases'][0]['audio_file']))
        self.assertGreater(len(pcm), 16000)
        self.assertEqual(len(pcm) % 2, 0)

    def test_changed_archive_is_rejected_before_transcription(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'bad.zip'
            path.write_bytes(b'not the source archive')
            with self.assertRaisesRegex(ValueError, 'differs'):
                verify_archive(path, self.manifest)


class NaturalConditionTests(unittest.TestCase):
    def test_new_phrasings_and_self_corrections(self):
        fixtures = [
            ('과일 스무디 아무거나 두 개만', {'requested_count': 2, 'included_categories': ['스무디']}),
            ('3가지 추천 부탁해요', {'requested_count': 3}),
            ('세 개 아니 두 개만 골라줘요', {'requested_count': 2}),
            ('팔천 원 아니 육천 원 이하로요', {'max_price_krw': 6000}),
            ('차가운 커피 팔천 원 아니 육천 원 이하', {'temperature': 'COLD', 'max_price_krw': 6000}),
            ('오천 원대 음료 세 개요', {'min_price_krw': 5000, 'max_price_krw': 5999, 'requested_count': 3}),
            ('구천 원보다 싼 거요', {'max_price_krw': 8999}),
            ('삼천 원에서 오천 원 사이 추천', {'min_price_krw': 3000, 'max_price_krw': 5000}),
            ('아이스 말고 따뜻한 라떼로요', {'temperature': 'HOT'}),
            ('찬 거 마시면 불편해서 따뜻한 걸로요', {'temperature': 'HOT'}),
            ('커피 말고 스무디로 주세요', {'excluded_categories': ['커피'], 'included_categories': ['스무디']}),
            ('우유 없는 음료', {'milk_free': True}),
            ('커피 빼지 말고', {'excluded_categories': []}),
        ]
        for text, expected in fixtures:
            actual = derive_conditions(text)
            with self.subTest(text=text): self.assertEqual({k: actual[k] for k in expected}, expected)

    def test_explicit_count_limits_schema_and_defensive_result(self):
        rows = menus()
        context = direct.prepare_context('스무디 두 개만 추천', rows, json.loads(direct.DEFAULT_EVIDENCE.read_text()))
        payload = direct.build_request(context, 'fixture')
        self.assertEqual(payload['text']['format']['schema']['properties']['recommendations']['maxItems'], 2)
        smoothie_rows = [m for m in rows if '스무디' in m['name']]
        value = candidate()
        value['recommendations'] = [{'menu_id': m['menu_id'], 'temperature': 'COLD', 'basis_fields': ['name']}
                                    for m in smoothie_rows]
        result = direct.validate_response(value, context)
        self.assertEqual(len(result['recommendations']), 2)
        self.assertEqual([r['menu_id'] for r in result['recommendations']], [m['menu_id'] for m in smoothie_rows[:2]])
        wrong = candidate('cafe_latte', 'HOT')
        with self.assertRaisesRegex(direct.DirectError, 'INELIGIBLE_OPTION'):
            direct.validate_response(wrong, context)

    def test_joint_order_budget_is_not_a_per_drink_budget(self):
        rows = menus()
        context = direct.prepare_context('두 잔 합쳐서 팔천 원 안으로', rows, json.loads(direct.DEFAULT_EVIDENCE.read_text()))
        self.assertIsNone(context['guard']['max_price_krw'])
        self.assertEqual(context['guard']['total_budget_krw'], 8000)
        with self.assertRaisesRegex(direct.DirectError, 'UNRESOLVED_HARD_CONDITION'):
            direct.validate_response(candidate(), context)

    def test_required_option_is_checked_against_actual_variant_choices(self):
        rows = menus()
        for row in rows:
            row['variants'] = [{'temperature': t, 'option_groups': []} for t in row['available_temperatures']]
        latte = next(m for m in rows if m['menu_id'] == 'cafe_latte')
        latte['variants'][0]['option_groups'] = [{'choices': [
            {'id': 'milk:soy', 'label': '두유 변경', 'price_delta_krw': 500}]}]  # Synthetic option, not real catalogue.
        context = direct.prepare_context('두유로 바꿀 수 있는 라떼', rows, json.loads(direct.DEFAULT_EVIDENCE.read_text()))
        self.assertEqual(context['allowed']['cafe_latte'], [latte['variants'][0]['temperature']])
        unsupported = next(m for m in rows if m['menu_id'] == 'vanilla_latte')
        self.assertEqual(context['allowed'][unsupported['menu_id']], [])

    def test_excluding_coffee_also_excludes_decaf_coffee_without_claiming_caffeine_zero(self):
        rows = menus()
        context = direct.prepare_context('커피도 차도 싫어요', rows, json.loads(direct.DEFAULT_EVIDENCE.read_text()))
        self.assertIsNone(context['guard']['max_caffeine_mg'])
        self.assertEqual(context['allowed']['decaf_americano'], [])
        self.assertEqual(context['allowed']['citron_tea'], [])
