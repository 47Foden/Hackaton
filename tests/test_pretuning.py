import unittest
from common.menu_data import MENUS, TASTE_ATTRIBUTES
from pretuning import binary_frame, validate_scores, continuous_frame

class FramesTest(unittest.TestCase):
    def test_binary(self):
        frame = binary_frame()
        self.assertEqual(frame.shape, (11, 5))
        self.assertEqual(frame.loc['카페라떼', ['커피', '라떼', '논커피라떼']].tolist(), [1, 1, 0])
        self.assertEqual(frame.loc['말차라떼', ['커피', '라떼', '논커피라떼']].tolist(), [0, 1, 1])

    def test_mean_and_normalization(self):
        runs = [validate_scores({'menus': [dict(name=m, **{a: score for a in TASTE_ATTRIBUTES}) for m in MENUS]}) for score in [0, 2, 4, 6, 8]]
        frame = continuous_frame(runs)
        self.assertAlmostEqual(frame.iloc[0]['단맛'], .4)
        self.assertEqual(list(frame.columns), TASTE_ATTRIBUTES)
        self.assertEqual(frame.shape, (11, 3))
        with self.assertRaises(ValueError):
            continuous_frame(runs[:4])
        with self.assertRaises(ValueError):
            validate_scores({'menus': []})
        with self.assertRaises(ValueError):
            validate_scores({'menus': [dict(name=m, 단맛=11, 신맛=0, 쓴맛=0) for m in MENUS]})

if __name__ == '__main__':
    unittest.main()
