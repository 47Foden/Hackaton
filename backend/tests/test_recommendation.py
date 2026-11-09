import unittest
from app.services.recommendation import SCORE_MENU_IDS, load_scores, parse_preferences, recommend

class RecommendationTests(unittest.TestCase):
    def setUp(self):
        self.menus = [{'menu_id':mid, 'name':name, 'is_available':True, 'price_krw':3000,
                       'available_temperatures':['HOT','COLD']} for name,mid in SCORE_MENU_IDS.items()]

    def test_actual_csv_ranking_and_negative_order(self):
        scores,_ = load_scores()
        expected = sorted(self.menus, key=lambda m: (-scores[m['menu_id']]['단맛'], m['menu_id']))
        self.assertEqual(recommend('달달한 음료',self.menus), [m['menu_id'] for m in expected[:4]])
        expected = sorted(self.menus, key=lambda m: (scores[m['menu_id']]['단맛'], m['menu_id']))
        for phrase in ['안 단 음료','덜 단 음료','단맛이 적은 음료','달지 않은 음료']:
            self.assertEqual(recommend(phrase,self.menus),[m['menu_id'] for m in expected[:4]],phrase)

    def test_scoped_negation(self):
        tastes,_,_,_ = parse_preferences('달지 않고 신맛 있는 음료')
        self.assertEqual(tastes, {'단맛':-1,'신맛':1})
        self.assertIsNone(parse_preferences('차갑고 달달한 음료')[1])
        self.assertEqual(parse_preferences('차갑고 달달한 티 종류 아무거나')[1], '티')

    def test_catalog_name_changes_and_unscored_menus(self):
        americano = next(menu for menu in self.menus if menu['menu_id'] == 'iced_americano')
        americano['name'] = '아메리카노'
        new_menu = {**americano, 'menu_id': 'decaf_americano', 'name': '디카페인 아메리카노'}
        self.assertEqual(recommend('추천', [americano, new_menu]), ['iced_americano'])

    def test_price_availability_empty_and_unsupported(self):
        self.assertEqual(recommend('2000원 이하 달달한 음료',self.menus), [])
        self.menus[0]['is_available'] = False
        self.assertNotIn(self.menus[0]['menu_id'],recommend('추천',self.menus))
        with self.assertRaises(ValueError): recommend('카페인 적은 음료',self.menus)
        with self.assertRaises(ValueError): recommend('안녕하세요',self.menus)
