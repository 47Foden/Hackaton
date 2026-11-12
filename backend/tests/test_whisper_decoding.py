import unittest
from unittest.mock import Mock
from app.services.voice.whisper_worker import decoding_options, CAFE_VOCABULARY

class WhisperDecodingTests(unittest.TestCase):
    def test_vocabulary_prompt_device_and_repeated_syllables(self):
        processor = Mock()
        options = decoding_options(processor, 'cuda:0')
        processor.get_prompt_ids.assert_called_once_with(CAFE_VOCABULARY, return_tensors='pt')
        processor.get_prompt_ids.return_value.to.assert_called_once_with('cuda:0')
        self.assertIs(options['prompt_ids'], processor.get_prompt_ids.return_value.to.return_value)
        self.assertEqual(options['no_repeat_ngram_size'], 0)
        self.assertEqual(options['repetition_penalty'], 1.0)
        self.assertEqual(options['language'], 'ko')
        for word in ['아아', '아샷추', '복숭아 아이스티']:
            self.assertIn(word, CAFE_VOCABULARY)
