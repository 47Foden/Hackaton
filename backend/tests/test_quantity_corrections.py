import unittest
import test_voice_intent as intent_tests
from test_voice_options import menu

class QuantityCorrectionTests(unittest.TestCase):
    def setUp(self):
        self.api = intent_tests.VoiceIntentTests()
        self.rows = [{**menu(), 'menu_id':'iced_americano','name':'아메리카노'},menu()]

    def post(self,text,**kwargs):
        status,body,_,_=self.api.post(text,'order',rows=self.rows,**kwargs)
        self.assertEqual(status,200)
        return body['action']

    def test_corrections_replace_quantity_not_menu(self):
        for clause,quantity in [('한 잔 말고 두 잔',2),('1잔 말고 2잔',2),
                                ('두 잔 아니고 세 잔',3),('두 잔 아니라 한 잔',1),
                                ('한 잔 말고 두 잔 말고 세 잔',3),('두 잔 대신 네 잔',4)]:
            with self.subTest(clause=clause):
                action=self.post('아메리카노 '+clause)
                if quantity==1:
                    self.assertEqual(action['menu_id'],'iced_americano')
                else:
                    self.assertEqual([(i['menu_id'],i['quantity']) for i in action['items']],[('iced_americano',quantity)])

    def test_separate_menu_exclusion_still_works(self):
        action=self.post('아메리카노 한 잔 말고 카페라떼 두 잔')
        self.assertEqual([(i['menu_id'],i['quantity']) for i in action['items']],[('cafe_latte',2)])

    def test_multiple_menu_corrections_keep_options_and_temperature(self):
        action=self.post('아이스 아메리카노 한 잔 말고 두 잔 샷 추가 그리고 따뜻한 카페라떼 두 잔 말고 세 잔')
        first,second=action['items']
        self.assertEqual((first['menu_id'],first['quantity'],first['temperature'],first['option_ids']),('iced_americano',2,'COLD',['shot:extra']))
        self.assertEqual((second['menu_id'],second['quantity'],second['temperature']),('cafe_latte',3,'HOT'))

    def test_explicit_corrected_quantity_wins_over_wrong_model(self):
        parsed={'items':[{'menu_id':'iced_americano','menu_phrase':'아메리카노','quantity':1,
                          'temperature':None,'option_ids':None,'unresolved_fields':[]}],
                'service_type':None,'unresolved_fields':[]}
        action=self.post('아메리카노 한 잔 말고 두 잔',order_result=parsed)
        self.assertEqual(action['items'][0]['quantity'],2)
        parsed['items'][0]['quantity']=2
        action=self.post('아메리카노 두 잔 말고 한 잔',order_result=parsed)
        self.assertEqual(action['type'],'select_menu')

    def test_corrected_quantity_bounds(self):
        for count in [0,100]:
            action=self.post('아메리카노 한 잔 말고 '+str(count)+'잔')
            self.assertEqual(action['type'],'retry')
            self.assertEqual(action['reason'],'INVALID_OPTION')
