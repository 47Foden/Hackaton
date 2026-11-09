import asyncio
import os
import unittest
from threading import Thread
from unittest.mock import patch
from urllib.error import URLError

from app.services.voice.interpretation import interpret_transcript
from app.services.voice.transcription import TranscriptionError, transcribe_voice
from app.services.voice.whisper_worker import WhisperWorker
from test_voice_audio import MIME_TYPE, post_audio, webm_audio

MENU_ROWS = [
    {"menu_id": "cafe_latte", "name": "카페라떼", "is_available": True, "available_temperatures": ["HOT", "COLD"]},
    {"menu_id": "iced_americano", "name": "아이스아메리카노", "is_available": True, "available_temperatures": ["COLD"]},
    {"menu_id": "lemon_tea", "name": "레몬차", "is_available": False, "available_temperatures": ["HOT"]},
    {"menu_id": "lemon_tea_alias", "name": "레몬티", "is_available": True, "available_temperatures": ["HOT"]},
]
for menu in MENU_ROWS:
    menu["price_krw"] = 3000
MENUS = {menu["menu_id"]: menu for menu in MENU_ROWS}


class InterpretationTests(unittest.TestCase):
    def test_confirmation_is_explicit_and_stage_scoped(self):
        for stage in ('menu_confirmation', 'review'):
            self.assertEqual(interpret_transcript('네', stage, MENUS).type, 'confirm')
            self.assertEqual(interpret_transcript('주문 확정', stage, MENUS).type, 'confirm')
            self.assertEqual(interpret_transcript('아니요', stage, MENUS).type, 'retry')
        self.assertEqual(interpret_transcript('네', 'menu', MENUS).type, 'retry')

    def test_stage_options_require_valid_values_and_available_menu(self):
        def action(text, stage, menu):
            return interpret_transcript(text, stage, MENUS, selected_menu_id=menu).model_dump()

        self.assertEqual(action("따뜻하게 해 주세요.", "temperature", "cafe_latte"),
                         {"type": "set_temperature", "temperature": "HOT"})
        self.assertEqual(action("따뜻하게", "temperature", "iced_americano")["reason"], "INVALID_OPTION")
        self.assertEqual(action("매장에서 마실게요.", "service_type", "cafe_latte"),
                         {"type": "set_service_type", "service_type": "DINE_IN"})
        self.assertEqual(action("포장해 주세요.", "service_type", "lemon_tea")["reason"], "MENU_UNAVAILABLE")

    def test_menu_selection_is_exact_and_taste_phrase_returns_filters(self):
        self.assertEqual(interpret_transcript("레몬 티 주세요.", "menu", MENUS).menu_id, "lemon_tea_alias")
        self.assertEqual(interpret_transcript("레몬차 주세요.", "menu", MENUS).reason, "MENU_UNAVAILABLE")
        self.assertEqual(interpret_transcript("레몬티 말고 카페라떼?", "menu", MENUS).reason, "UNRECOGNIZED")
        self.assertEqual(interpret_transcript("...", "menu", MENUS).reason, "EMPTY_TRANSCRIPT")
        self.assertEqual(interpret_transcript("달지 않은 차 추천해 주세요.", "menu", MENUS).model_dump(),
                         {"type": "recommend", "filters": {"tea": 1}, "targets": {"sweetness": 0.2}})

    def test_candidate_selection_cannot_escape_current_list(self):
        candidates = ("cafe_latte", "iced_americano")
        self.assertEqual(interpret_transcript("두 번째 주세요.", "recommendations", MENUS,
                                              candidate_menu_ids=candidates).menu_id, "iced_americano")
        self.assertEqual(interpret_transcript("레몬티", "recommendations", MENUS,
                                              candidate_menu_ids=candidates).reason, "OUTSIDE_CANDIDATES")


class VoiceInterpretApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio = webm_audio()

    def post(self, fields):
        with patch("app.routers.voice.list_menus", return_value=MENU_ROWS):
            return asyncio.run(post_audio(self.audio, "recording.webm", MIME_TYPE,
                                          path="/api/voice/interpret", fields=fields))

    def test_preference_audio_returns_ranked_candidates_and_restart(self):
        with patch("app.routers.voice.transcribe_voice", return_value="덜 단 커피"):
            status, body = self.post([("stage", "menu")])
        self.assertEqual(status, 200)
        self.assertEqual(body["action"], {"type": "recommendation_results", "menu_ids": ["iced_americano", "cafe_latte"]})
        with patch("app.routers.voice.transcribe_voice", return_value="다시 추천"):
            status, body = self.post([("stage", "recommendations"), ("candidate_menu_ids", "cafe_latte")])
        self.assertEqual(body["action"]["type"], "restart_recommendation")

    def test_repeated_fields_keep_display_order_and_send_pcm_to_transcriber(self):
        fields = [("stage", "recommendations"), ("candidate_menu_ids", "cafe_latte"),
                  ("candidate_menu_ids", "iced_americano")]
        with patch("app.routers.voice.transcribe_voice", return_value="두 번째 주세요.") as transcribe:
            status, body = self.post(fields)
        self.assertEqual(status, 200)
        self.assertEqual(body, {"transcript": "두 번째 주세요.", "action": {"type": "select_menu", "menu_id": "iced_americano"}})
        self.assertEqual(len(transcribe.call_args.args[0]), 16000 * 2)

    def test_invalid_stage_and_context_rejected_before_transcription(self):
        for fields in ([], [("stage", "submitting")], [("stage", "temperature")],
                       [("stage", "menu"), ("selected_menu_id", "cafe_latte")],
                       [("stage", "service_type"), ("selected_menu_id", "unknown")],
                       [("stage", "recommendations"), ("candidate_menu_ids", "cafe_latte"),
                        ("candidate_menu_ids", "cafe_latte")]):
            with self.subTest(fields=fields), patch("app.routers.voice.transcribe_voice") as transcribe:
                status, _ = self.post(fields)
                self.assertEqual(status, 422)
                transcribe.assert_not_called()

    def test_transcription_timeout_maps_to_504_and_releases_slot(self):
        error = TranscriptionError(504, "TRANSCRIPTION_TIMEOUT", "timeout")
        with patch("app.routers.voice.transcribe_voice", side_effect=[error, ""]):
            status, body = self.post([("stage", "menu")])
            self.assertEqual(status, 504)
            self.assertEqual(body["detail"]["code"], "TRANSCRIPTION_TIMEOUT")
            self.assertEqual(self.post([("stage", "menu")]),
                             (200, {"transcript": "", "action": {"type": "retry", "reason": "EMPTY_TRANSCRIPT"}}))


class TranscriptionTransportTests(unittest.TestCase):
    def test_worker_transport_passes_raw_pcm_without_model_dependencies(self):
        received = []

        def transcribe(pcm):
            received.append(pcm)
            return "차갑게"

        with WhisperWorker(("127.0.0.1", 0), transcribe) as worker:
            thread = Thread(target=worker.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.dict(os.environ, {"VOICE_TRANSCRIPTION_URL": f"http://127.0.0.1:{worker.server_port}/transcribe"}):
                    self.assertEqual(transcribe_voice(b"\x01\x00"), "차갑게")
                    with worker.slot, self.assertRaises(TranscriptionError) as busy:
                        transcribe_voice(b"\x01\x00")
                    self.assertEqual((busy.exception.status, busy.exception.code), (503, "TRANSCRIPTION_BUSY"))
                self.assertEqual(received, [b"\x01\x00"])
            finally:
                worker.shutdown()
                thread.join()

    def test_worker_client_timeout_is_reported_as_504(self):
        with patch.dict(os.environ, {"VOICE_TRANSCRIPTION_URL": "http://127.0.0.1:8765/transcribe"}), \
                patch("app.services.voice.transcription.urlopen", side_effect=URLError(TimeoutError())):
            with self.assertRaises(TranscriptionError) as raised:
                transcribe_voice(b"\x00\x00")
        self.assertEqual(raised.exception.status, 504)
