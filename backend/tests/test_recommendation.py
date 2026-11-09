import unittest
import csv
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from app.services.recommendation import SCORE_MENU_IDS, load_scores, parse_preferences, recommend

class RecommendationTests(unittest.TestCase):
    def setUp(self):
        # Synthetic test scores only; no generated taste results are committed.
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name) / 'recommendation'
        root.mkdir()
        actual = Path(__file__).resolve().parents[2] / 'common' / 'recommendation' / 'binary.csv'
        (root / 'binary.csv').write_bytes(actual.read_bytes())
        with (root / 'continuous.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['메뉴', '단맛', '신맛', '쓴맛'])
            for i, name in enumerate(SCORE_MENU_IDS):
                writer.writerow([name, i / len(SCORE_MENU_IDS), .2, .3])
        env = patch.dict(os.environ, {'COMMON_DIR': temp.name})
        env.start()
        self.addCleanup(env.stop)
        self.root = root
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

    def test_all_45_menus_supported_and_unknown_menu_ignored(self):
        self.assertEqual(len(load_scores()[0]), 45)
        decaf = next(menu for menu in self.menus if menu['menu_id'] == 'decaf_americano')
        unknown = {**decaf, 'menu_id': 'unknown'}
        self.assertEqual(recommend('디카페인 추천', [decaf, unknown]), ['decaf_americano'])

    def test_missing_and_legacy_scores_rejected(self):
        path = self.root / 'continuous.csv'
        path.unlink()
        with self.assertRaisesRegex(ValueError, '아직 준비되지'):
            load_scores()
        path.write_text('메뉴,단맛,신맛,쓴맛\n아메리카노,0,0,0\n', encoding='utf-8-sig')
        with self.assertRaises(ValueError):
            load_scores()

    def test_price_availability_empty_and_unsupported(self):
        self.assertEqual(recommend('2000원 이하 달달한 음료',self.menus), [])
        self.menus[0]['is_available'] = False
        self.assertNotIn(self.menus[0]['menu_id'],recommend('추천',self.menus))
        with self.assertRaises(ValueError): recommend('카페인 적은 음료',self.menus)
        with self.assertRaises(ValueError): recommend('안녕하세요',self.menus)
