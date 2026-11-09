import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from common.menu_data import MENUS, TASTE_ATTRIBUTES, BINARY_ATTRIBUTES
from pretuning import binary_frame, validate_scores, continuous_frame, prepare, generate

class FramesTest(unittest.TestCase):
    def test_binary(self):
        frame = binary_frame()
        self.assertEqual(frame.shape, (45, 12))
        self.assertEqual(frame.loc['카페라떼', ['커피', '라떼', '논커피라떼']].tolist(), [1, 1, 0])
        self.assertEqual(frame.loc['녹차라떼', ['커피', '라떼', '논커피라떼']].tolist(), [0, 0, 1])

    def test_mean_and_normalization(self):
        runs = [validate_scores({'menus': [dict(name=m, **{a: score for a in TASTE_ATTRIBUTES}) for m in MENUS]}) for score in [0, 2, 4, 6, 8]]
        frame = continuous_frame(runs)
        self.assertAlmostEqual(frame.iloc[0]['단맛'], .4)
        self.assertEqual(list(frame.columns), TASTE_ATTRIBUTES)
        self.assertEqual(frame.shape, (45, 3))
        with self.assertRaises(ValueError):
            continuous_frame(runs[:4])
        with self.assertRaises(ValueError):
            validate_scores({'menus': []})
        with self.assertRaises(ValueError):
            validate_scores({'menus': [dict(name=m, 단맛=11, 신맛=0, 쓴맛=0) for m in MENUS]})

    def test_catalogue_categories_cover_new_menus(self):
        frame = binary_frame()
        self.assertEqual(frame.loc['디카페인 카페라떼', ['커피', '디카페인', '라떼']].tolist(), [0, 1, 1])
        self.assertEqual(frame.loc['딸기주스', ['스무디', '주스']].tolist(), [0, 1])
        self.assertEqual(frame.loc['딸기요거트스무디', ['스무디', '주스']].tolist(), [1, 0])
        self.assertTrue((frame.sum(axis=1) == 2).all())
        self.assertEqual(list(frame.columns), BINARY_ATTRIBUTES)

    def test_prepare_never_publishes_unscored_tastes(self):
        with tempfile.TemporaryDirectory() as temp:
            out = prepare(Path(temp) / 'new')
            self.assertTrue((out / 'binary.csv').exists())
            self.assertFalse((out / 'continuous.csv').exists())
            self.assertEqual(json.loads((out / 'metadata.json').read_text())['status'], 'prepared')
            with self.assertRaises(FileExistsError):
                prepare(out)

    def test_five_evaluations_produce_mean_and_preserve_snapshot(self):
        runs = [validate_scores({'menus': [dict(name=m, **{a: v for a in TASTE_ATTRIBUTES}) for m in MENUS]})
                for v in [0, 2, 4, 6, 8]]
        with tempfile.TemporaryDirectory() as temp, patch.dict('os.environ', {'OPENAI_API_KEY': 'test-only'}), \
                patch('pretuning.api_request', return_value={}), \
                patch('pretuning.evaluate', side_effect=[(r, {}) for r in runs]) as evaluate:
            out = Path(temp) / 'new'
            generate(out, 'test-model')
            self.assertEqual(evaluate.call_count, 5)
            import pandas as pd
            frame = pd.read_csv(out / 'continuous.csv', index_col=0)
            self.assertEqual(frame.shape, (45, 3))
            self.assertAlmostEqual(frame.iloc[0]['단맛'], .4)
            self.assertNotIn('가격', frame.columns)
            self.assertEqual(json.loads((out / 'metadata.json').read_text())['status'], 'completed')

if __name__ == '__main__':
    unittest.main()
