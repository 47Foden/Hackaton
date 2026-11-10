import unittest
from app.services.voice.cart import parse_cart

class VoiceCartTests(unittest.TestCase):
    def setUp(self):
        self.menus = {k: dict(name=n, is_available=True, available_temperatures=["HOT","COLD"], variants=[dict(temperature="COLD", option_groups=[dict(choices=[dict(id="shot:extra",label="샷 추가")])])]) for k,n in [("americano","아메리카노"),("latte","카페라떼"),("vanilla","바닐라 아메리카노")]}
    def test_multiple_quantities_temperature_options(self):
        result = parse_cart("아이스 아메리카노 두 잔 샷 추가 그리고 따뜻하게 카페라떼 한 잔", self.menus)
        self.assertEqual([(x.menu_id,x.quantity,x.temperature) for x in result.items], [("americano",2,"COLD"),("latte",1,"HOT")])
        self.assertEqual(result.items[0].option_ids, ["shot:extra"])
        self.assertEqual(result.items[1].option_ids, [])
    def test_longest_name(self):
        result=parse_cart("바닐라 아메리카노 2잔 아메리카노 1잔",self.menus)
        self.assertEqual([x.menu_id for x in result.items],["vanilla","americano"])
    def test_recommendation_not_order(self):
        self.assertIsNone(parse_cart("아메리카노 같은 메뉴 두개 추천",self.menus))
    def test_quantity_bounds(self):
        self.assertIsNone(parse_cart("아메리카노 100잔",self.menus))
