import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from common.menu_data import MENUS, TASTE_ATTRIBUTES, BINARY_ATTRIBUTES
from pretuning import rebuild


class RebuildTest(unittest.TestCase):
    def test_saved_scores_without_api_or_prices(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / 'old'
            source.mkdir()
            for i, score in enumerate([0, 2, 4, 6, 8], 1):
                data = {'menus': [dict(name=m, **{a: score for a in TASTE_ATTRIBUTES}) for m in MENUS]}
                response = {'status': 'completed', 'output': [{'type': 'message', 'content': [
                    {'type': 'output_text', 'text': json.dumps(data)}]}]}
                (source / f'run_{i}.json').write_text(json.dumps(response))
            out = Path(tmp) / 'new'
            with patch('pretuning.api_request') as api:
                rebuild(source, out)
                api.assert_not_called()
            frame = pd.read_csv(out / 'continuous.csv', index_col=0)
            self.assertEqual(list(frame.columns), TASTE_ATTRIBUTES)
            self.assertEqual(frame.shape, (len(MENUS), 3))
            self.assertAlmostEqual(frame.iloc[0]['단맛'], .4)
            self.assertEqual(pd.read_csv(out / 'binary.csv', index_col=0).shape, (len(MENUS), len(BINARY_ATTRIBUTES)))
            with self.assertRaises(FileExistsError):
                rebuild(source, out)
