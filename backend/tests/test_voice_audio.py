import asyncio
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.main import app
from app.services.voice.audio import MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS, SAMPLE_RATE_HZ, prepare_voice_audio

MIME_TYPE = "audio/webm;codecs=opus"


def webm_audio(duration=1, codec="libopus", container="webm"):
    return subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", f"sine=frequency=440:sample_rate=48000:duration={duration}",
        "-c:a", codec, "-f", container, "pipe:1",
    ], check=True, capture_output=True).stdout


async def post_audio(audio, filename, mime_type, before_upload=None):
    boundary = "voice-audio-test-boundary"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="audio"; filename="{filename}"\r\n'
            f"Content-Type: {mime_type}\r\n\r\n").encode() + audio + f"\r\n--{boundary}--\r\n".encode()
    messages = []

    async def receive():
        if before_upload:
            await before_upload()
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        messages.append(message)

    await app({
        "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
        "method": "POST", "scheme": "http", "path": "/api/voice/audio", "raw_path": b"/api/voice/audio",
        "query_string": b"", "root_path": "",
        "headers": [(b"content-type", f"multipart/form-data; boundary={boundary}".encode())],
        "server": ("testserver", 80), "client": ("127.0.0.1", 12345),
    }, receive, send)
    status = next(message["status"] for message in messages if message["type"] == "http.response.start")
    return status, json.loads(b"".join(message.get("body", b"") for message in messages if message["type"] == "http.response.body"))


class VoiceAudioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audio = webm_audio()

    def test_multipart_preserves_mime_and_converts_stream_without_duration_metadata(self):
        status, body = asyncio.run(post_audio(self.audio, "recording.webm", MIME_TYPE))
        self.assertEqual(status, 200)
        self.assertEqual(body, {
            "mime_type": MIME_TYPE, "container": "webm", "codec": "opus", "duration_seconds": 1.0,
            "size_bytes": len(self.audio), "source_sample_rate_hz": 48000, "source_channels": 1,
            "sample_rate_hz": SAMPLE_RATE_HZ, "channels": 1,
        })
        prepared = prepare_voice_audio(self.audio, "recording.webm", MIME_TYPE)
        self.assertEqual(len(prepared.pcm_s16le), SAMPLE_RATE_HZ * 2)

    def test_rejects_wrong_extension_mime_container_and_codec(self):
        for audio, filename, mime_type, code in (
            (self.audio, "recording.mp3", MIME_TYPE, "UNSUPPORTED_AUDIO"),
            (self.audio, "recording.webm", "audio/mp4", "UNSUPPORTED_AUDIO"),
            (webm_audio(container="matroska"), "recording.webm", MIME_TYPE, "AUDIO_FORMAT_MISMATCH"),
            (webm_audio(codec="libvorbis"), "recording.webm", MIME_TYPE, "AUDIO_FORMAT_MISMATCH"),
        ):
            with self.subTest(filename=filename, mime_type=mime_type, code=code):
                status, body = asyncio.run(post_audio(audio, filename, mime_type))
                self.assertEqual(status, 415)
                self.assertEqual(body["detail"]["code"], code)

    def test_limits_size_and_decoded_duration(self):
        for audio, code in (
            (b"x" * (MAX_AUDIO_BYTES + 1), "AUDIO_TOO_LARGE"),
            (b"x" * (MAX_AUDIO_BYTES + 16 * 1024), "AUDIO_TOO_LARGE"),
            (webm_audio(duration=MAX_AUDIO_SECONDS + 1), "AUDIO_TOO_LONG"),
        ):
            with self.subTest(code=code):
                status, body = asyncio.run(post_audio(audio, "recording.webm", MIME_TYPE))
                self.assertEqual(status, 413)
                self.assertEqual(body["detail"]["code"], code)

    def test_concurrent_request_is_rejected_while_slot_is_occupied(self):
        async def send_concurrent():
            started = asyncio.Event()
            release = asyncio.Event()

            async def pause_upload():
                started.set()
                await release.wait()

            active = asyncio.create_task(post_audio(self.audio, "recording.webm", MIME_TYPE, pause_upload))
            await started.wait()
            try:
                busy = await post_audio(self.audio, "recording.webm", MIME_TYPE)
            finally:
                release.set()
            return busy, await active

        busy, accepted = asyncio.run(send_concurrent())
        self.assertEqual(busy[0], 503)
        self.assertEqual(busy[1]["detail"]["code"], "AUDIO_BUSY")
        self.assertEqual(accepted[0], 200)

    def test_upload_timeout_releases_slot(self):
        async def pause_upload():
            await asyncio.Event().wait()

        with patch("app.routers.voice.UPLOAD_TIMEOUT_SECONDS", 0.01):
            status, body = asyncio.run(post_audio(self.audio, "recording.webm", MIME_TYPE, pause_upload))
        self.assertEqual(status, 408)
        self.assertEqual(body["detail"]["code"], "AUDIO_UPLOAD_TIMEOUT")
        self.assertEqual(asyncio.run(post_audio(self.audio, "recording.webm", MIME_TYPE))[0], 200)

    def test_probe_and_conversion_share_one_timeout_budget(self):
        probe = SimpleNamespace(stdout=json.dumps({
            "format": {"format_name": "matroska,webm"},
            "streams": [{"codec_type": "audio", "codec_name": "opus", "sample_rate": "48000", "channels": 1}],
        }).encode())
        with patch("app.services.voice.audio.monotonic", side_effect=[10, 11, 16]), \
                patch("app.services.voice.audio.subprocess.run", return_value=probe) as tool:
            status, body = asyncio.run(post_audio(self.audio, "recording.webm", MIME_TYPE))
        self.assertEqual(status, 504)
        self.assertEqual(body["detail"]["code"], "AUDIO_TIMEOUT")
        tool.assert_called_once()
        self.assertEqual(tool.call_args.kwargs["timeout"], 4)
