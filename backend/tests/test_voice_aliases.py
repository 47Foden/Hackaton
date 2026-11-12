import unittest
from app.services.voice.aliases import expand_order_aliases
from app.services.voice.options import extract_options
import test_voice_intent as intent_tests
from app.db.catalog import load_catalog
from test_voice_llm_integration import menus

class AliasRoutes(unittest.TestCase):
    def setUp(self):
        self.rows = menus()
        for row, catalog in zip(self.rows, load_catalog()):
            row['variants'] = [{'temperature': temp, 'option_groups': catalog.option_groups} for temp, _ in catalog.variants]
        self.api = intent_tests.VoiceIntentTests()

    def post(self, text):
        status, body, _, _ = self.api.post(text, 'order', rows=self.rows)
        self.assertEqual(status, 200)
        self.assertEqual(body['transcript'], text)
        return body

    def test_shorthand_menu_temperature_and_shot(self):
        for alias, mid, temperature, ids in [
            ('아아','iced_americano','COLD',[]),
            ('뜨아','iced_americano','HOT',[]),
            ('아샷추','peach_iced_tea','COLD',['shot:extra']),
            ('아카라','cafe_latte','COLD',[]),
            ('아바라','vanilla_latte','COLD',[]),
            ('블요스','blueberry_yogurt_smoothie',None,[]),
            ('망요스','mango_yogurt_smoothie',None,[]),
            ('딸요스','strawberry_yogurt_smoothie',None,[]),
        ]:
            with self.subTest(alias=alias):
                body=self.post(alias+' 주세요')
                self.assertEqual(body['action']['type'],'select_menu')
                self.assertEqual(body['action']['menu_id'],mid)
                options=body.get('recognized_options',{})
                if temperature: self.assertEqual(options['temperature'],temperature)
                if ids:
                    self.assertEqual(options['customization']['option_ids'],ids)
                    menu=next(m for m in self.rows if m['menu_id']==mid)
                    shot=next(c for v in menu['variants'] for g in v['option_groups'] for c in g['choices'] if c['id']=='shot:extra')
                    self.assertEqual(shot['price_delta_krw'],600)

    def test_size_and_quantity_on_individual_lines(self):
        body=self.post('아샷추 두 잔 크게 그리고 아바라 한 잔')
        items=body['action']['items']
        self.assertEqual([i['quantity'] for i in items],[2,1])
        self.assertEqual(set(items[0]['option_ids']),{'size:up','shot:extra'})
        self.assertEqual(items[1]['option_ids'],[])
        self.assertEqual(items[0]['temperature'],'COLD')

    def test_size_synonyms_and_negation(self):
        menu=next(m for m in self.rows if m['menu_id']=='peach_iced_tea')
        for phrase in ['크게','큰 사이즈','사이즈업','사이즈 업','라지 사이즈']:
            with self.subTest(phrase=phrase):
                body=self.post('복숭아 아이스티 '+phrase)
                self.assertIn('size:up',body['recognized_options']['customization']['option_ids'])
        options=extract_options('사이즈업 말고',menu=menu)
        self.assertTrue(options is None or options.customization is None or not options.customization.option_ids)

    def test_no_substitution_inside_other_words(self):
        self.assertEqual(expand_order_aliases('아아메리카노'), '아아메리카노')
        self.assertEqual(expand_order_aliases('아아2잔'), '아이스 아메리카노2잔')

    def test_observed_asr_variants_and_spaced_repetitions(self):
        for heard in ['아샤추', '아샤주', '아 샤 추', '아 샤 주', '아 샷 추']:
            with self.subTest(heard=heard):
                body = self.post(heard + ' 한 잔')
                self.assertEqual(body['action']['menu_id'], 'peach_iced_tea')
                self.assertEqual(body['recognized_options']['customization']['option_ids'], ['shot:extra'])
        for heard in ['아아', '아 아', '아  아']:
            with self.subTest(heard=heard):
                body = self.post(heard + ' 두 잔')
                self.assertEqual(body['action']['items'][0]['menu_id'], 'iced_americano')
                self.assertEqual(body['action']['items'][0]['temperature'], 'COLD')
                self.assertEqual(body['action']['items'][0]['quantity'], 2)

    def test_similar_generic_words_do_not_become_orders(self):
        for text in ['아', '아주', '아 샤', '아아아', '아샤주스', '좋아아', '아 샤 주스']:
            self.assertEqual(expand_order_aliases(text), text)
        text = expand_order_aliases('아샤추 말고 아 아 두 잔')
        self.assertEqual(text, '복숭아 아이스티 말고 아이스 아메리카노 두 잔')
        body = self.post('아샤추 말고 아 아 두 잔')
        self.assertEqual([item['menu_id'] for item in body['action']['items']], ['iced_americano'])
