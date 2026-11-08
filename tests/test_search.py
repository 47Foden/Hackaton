import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from common.menu_data import MENUS
from pretuning import search_sources, evaluate


def research(citations=True):
    return {'status': 'completed', 'output': [
        {'type': 'web_search_call', 'status': 'completed'},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': 'Research evidence',
         'annotations': [{'type': 'url_citation', 'url': 'https://example.com/menu'}] if citations else []}]}]}


class SearchTest(unittest.TestCase):
    def test_citation_fallback(self):
        self.assertEqual(search_sources(research())[0]['url'], 'https://example.com/menu')

    def test_action_sources(self):
        data = research(False)
        data['output'][0]['action'] = {'sources': [{'url': 'https://example.com/menu'}]}
        self.assertEqual(len(search_sources(data)), 1)

    def test_requires_actual_search(self):
        data = research()
        data['output'].pop(0)
        self.assertEqual(search_sources(data), [])

    def test_research_then_scoring(self):
        scores = {'menus': [dict(name=m, 단맛=5, 신맛=2, 쓴맛=0) for m in MENUS]}
        response = {'status': 'completed', 'output': [{'type': 'message', 'content': [
            {'type': 'output_text', 'text': json.dumps(scores)}]}]}
        with tempfile.TemporaryDirectory() as tmp, patch('pretuning.api_request', side_effect=[research(), response]) as api:
            frame, _ = evaluate('test-key', 'test-model', Path(tmp)/'research.json', Path(tmp)/'scores.json')
            self.assertEqual(frame.iloc[0]['단맛'], .5)
            self.assertEqual(api.call_count, 2)
            self.assertNotIn('text', api.call_args_list[0].args[2])
            self.assertNotIn('tools', api.call_args_list[1].args[2])
            self.assertEqual(api.call_args_list[1].args[2]['input'], 'Research evidence')

    def test_failed_research_saved_without_scoring(self):
        with tempfile.TemporaryDirectory() as tmp, patch('pretuning.api_request', return_value=research(False)) as api:
            path = Path(tmp)/'research.json'
            with self.assertRaisesRegex(ValueError, 'no verifiable sources'):
                evaluate('test-key', 'test-model', path)
            self.assertTrue(path.exists())
            self.assertEqual(api.call_count, 1)
