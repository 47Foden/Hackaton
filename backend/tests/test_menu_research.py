"""Official source parsing and taste regressions. No live LLM/network in tests."""
import copy
from datetime import date
import json
import unittest

from app.services.menu_research import parse_page, build_cache
from app.services import llm_direct as direct
from app.services.menu_evidence import validate_evidence
from app.db.catalog import load_catalog
from app.services.taste_evidence import supports_request
from app.services.recommendation_conditions import derive_conditions
from test_voice_llm_integration import menus, candidate


class OfficialResearchTests(unittest.TestCase):
    def test_parser_extracts_variant_description_without_external_price_import(self):
        html = '''<ul id="menu_list"><li><a><div class="cont_gallery_list_label">ICE</div>
        <img src="https://img.mega-mgccoffee.com/test.jpg"></a><div class="inner_modal">
        <div class="cont_text_box"><div class="cont_text inner_modal_title"><b>꿀아메리카노</b></div>
        <div class="cont_text">컵용량 710ml</div><div class="cont_text">달콤한 <b>사양벌꿀</b> 커피.</div>
        <div class="cont_text">가격 999원</div></div></div></li></ul>'''
        rows = parse_page(html, 'https://www.mega-mgccoffee.com/menu/menu.php?page=6')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['temperature'], 'COLD')
        self.assertEqual(rows[0]['description'], '달콤한 사양벌꿀 커피.')
        self.assertNotIn('price', rows[0])

    def test_cached_45_menus_and_71_variants_have_current_official_descriptions(self):
        data = json.loads(direct.DEFAULT_EVIDENCE.read_text())
        validate_evidence(data, load_catalog())
        audit = json.loads((direct.DEFAULT_EVIDENCE.parent / 'menu_research_audit.json').read_text())
        self.assertEqual(len(data['menus']), 45)
        self.assertEqual(len(audit['matched']), 71)
        self.assertEqual(audit['unmatched'], [])
        for menu in data['menus']:
            for variant in menu['variants'].values():
                self.assertEqual(variant['description']['status'], 'verified')
                self.assertTrue(variant['description']['source'].startswith('https://www.mega-mgccoffee.com/'))
                # Descriptions are not proof of ingredient exclusions or allergy safety.
                for field in ('milk', 'caffeine_mg', 'allergens'):
                    self.assertEqual(variant[field]['status'], 'unknown')

    def test_identity_mismatch_does_not_reuse_old_description_or_change_input(self):
        root = direct.DEFAULT_EVIDENCE.parent
        data = json.loads(direct.DEFAULT_EVIDENCE.read_text())
        original = copy.deepcopy(data)
        images = json.loads((root / 'menu_images.json').read_text())
        sources = json.loads((root / 'menu_image_sources.json').read_text())
        wrong = {'official_name': '아메리카노', 'temperature': 'COLD',
                 'image_source_url': 'https://img.mega-mgccoffee.com/different-recipe.jpg',
                 'description': '검증되지 않은 달콤함', 'source': 'https://www.mega-mgccoffee.com/menu/', 'page_sha256': 'fixture'}
        result, audit = build_cache(data, images, sources, [wrong], date.today().isoformat())
        self.assertEqual(audit['matched'], [])
        self.assertEqual(result['menus'][0]['variants']['COLD']['description']['status'], 'unknown')
        self.assertEqual(data, original)


class GroundedTasteTests(unittest.TestCase):
    def setUp(self):
        self.rows = menus()
        self.evidence = json.loads(direct.DEFAULT_EVIDENCE.read_text())

    def context(self, text):
        return direct.prepare_context(text, self.rows, self.evidence)

    def test_sweet_under_3000_excludes_plain_americano_and_allows_sweetened_basics(self):
        ctx = self.context('삼천 원 이하 달달한 음료')
        self.assertEqual(ctx['allowed']['iced_americano'], [])
        self.assertTrue(ctx['allowed']['honey_americano'])
        self.assertTrue(ctx['allowed']['vanilla_americano'])
        self.assertTrue(ctx['allowed']['hazelnut_americano'])
        self.assertEqual(ctx['allowed']['vanilla_latte'], [])  # Above local budget.
        payload = direct.build_request(ctx, 'fixture')
        ids = payload['text']['format']['schema']['properties']['recommendations']['items']['properties']['menu_id']['enum']
        self.assertNotIn('iced_americano', ids)
        for row in self.rows:
            if row['menu_id'] in ids: self.assertLessEqual(row['price_krw'], 3000)
        with self.assertRaisesRegex(direct.DirectError, 'INELIGIBLE_OPTION'):
            direct.validate_response(candidate(fields=['description']), ctx)
        valid = candidate('honey_americano', fields=['description', 'price_krw'])
        self.assertEqual(direct.validate_response(valid, ctx)['recommendations'][0]['menu_id'], 'honey_americano')

    def test_local_database_price_wins_and_taste_response_needs_description(self):
        next(row for row in self.rows if row['menu_id'] == 'honey_americano')['price_krw'] = 1234
        ctx = self.context('이천 원 이하 달콤한 음료')
        self.assertTrue(ctx['allowed']['honey_americano'])
        with self.assertRaisesRegex(direct.DirectError, 'DESCRIPTION_EVIDENCE_REQUIRED'):
            direct.validate_response(candidate('honey_americano', fields=['price_krw']), ctx)
        value = candidate('honey_americano', fields=['description', 'price_krw'])
        self.assertIn('1,234원', direct.validate_response(value, ctx)['recommendations'][0]['reason'])

    def test_fruit_smoothies_do_not_include_plain_yogurt(self):
        ctx = self.context('과일 스무디 두 개만')
        self.assertEqual(ctx['allowed']['plain_yogurt_smoothie'], [])
        for mid in ('strawberry_yogurt_smoothie', 'mango_yogurt_smoothie', 'blueberry_yogurt_smoothie'):
            self.assertTrue(ctx['allowed'][mid])
        self.assertEqual(direct.build_request(ctx, 'fixture')['text']['format']['schema']['properties']['recommendations']['maxItems'], 2)

    def test_excluded_fruits_do_not_become_required_flavors(self):
        for text, excluded in [
            ('레몬 말고 딸기', ['레몬']),
            ('레몬이랑 망고는 빼고 딸기', ['레몬', '망고']),
            ('레몬과 망고를 제외하고 딸기 음료 추천', ['레몬', '망고']),
            ('레몬 말고 망고 말고 딸기', ['레몬', '망고']),
        ]:
            with self.subTest(text=text):
                ctx = self.context(text)
                self.assertEqual(ctx['guard']['flavors'], ['딸기'])
                self.assertEqual(ctx['guard']['excluded_flavors'], excluded)
                self.assertTrue(ctx['allowed']['strawberry_yogurt_smoothie'])
                self.assertEqual(ctx['allowed']['mango_yogurt_smoothie'], [])
                self.assertEqual(ctx['allowed']['plain_yogurt_smoothie'], [])
                with self.assertRaisesRegex(direct.DirectError, 'INELIGIBLE_OPTION'):
                    direct.validate_response(candidate('mango_yogurt_smoothie', fields=['description']), ctx)

    def test_flavor_exclusion_rejects_blends_and_supports_exclusion_only(self):
        guard = derive_conditions('레몬이랑 망고는 빼고 딸기')
        def fields(value): return {'description': {'status': 'verified', 'value': value}}
        self.assertTrue(supports_request(guard, fields('달콤한 딸기 음료')))
        self.assertFalse(supports_request(guard, fields('딸기와 망고를 혼합한 음료')))
        only = derive_conditions('레몬은 빼고 추천')
        self.assertEqual(only['flavors'], [])
        self.assertEqual(only['excluded_flavors'], ['레몬'])
        self.assertFalse(supports_request(only, fields('상큼한 레몬 음료')))
        keep = derive_conditions('레몬은 빼지 말고 추천')
        self.assertEqual(keep['flavors'], ['레몬'])
        self.assertEqual(keep['excluded_flavors'], [])
        keep = derive_conditions('레몬은 제외하지 말고 추천')
        self.assertEqual(keep['excluded_flavors'], [])

    def test_sugar_free_is_not_treated_as_not_sweet(self):
        ctx = self.context('달달한 티')
        self.assertTrue(ctx['allowed']['zero_peach_iced_tea'])  # Official description explicitly lists substitute sweeteners.
        fields = {'description': {'status': 'verified', 'value': '달콤하지 않은 음료'}}
        self.assertFalse(supports_request(derive_conditions('달달한 음료'), fields))

    def test_unknown_taste_is_not_replaced_by_menu_name_or_extra_syrup(self):
        missing = copy.deepcopy(self.evidence)
        for variant in missing['menus'][1]['variants'].values():
            variant['description'] = {'status': 'unknown', 'value': None, 'source': None, 'checked_date': None, 'note': 'test only'}
        ctx = direct.prepare_context('달달한 음료', self.rows, missing)
        self.assertEqual(ctx['allowed']['honey_americano'], [])
