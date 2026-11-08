import json
import os
from http.client import HTTPException as HTTPProtocolError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

TRANSCRIPTION_TIMEOUT_SECONDS = 25


class TranscriptionError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


def transcribe_voice(pcm_s16le: bytes) -> str:
    worker_url = os.environ.get("VOICE_TRANSCRIPTION_URL")
    if not worker_url:
        raise TranscriptionError(503, "TRANSCRIPTION_UNAVAILABLE", "음성 전사 서버가 준비되지 않았어요.")

    try:
        request = Request(worker_url, data=pcm_s16le, method="POST", headers={"Content-Type": "application/octet-stream"})
        with urlopen(request, timeout=TRANSCRIPTION_TIMEOUT_SECONDS) as response:
            data = response.read(16_385)
        if len(data) > 16_384:
            raise ValueError("Transcript response too large")
        payload = json.loads(data)
        transcript = payload.get("transcript") if isinstance(payload, dict) else None
        if not isinstance(transcript, str):
            raise ValueError("Invalid transcript response")
        return transcript.strip()
    except HTTPError as error:
        error.close()
        if error.code == 503:
            raise TranscriptionError(503, "TRANSCRIPTION_UNAVAILABLE", "음성 전사 서버가 바빠요. 잠시 후 다시 녹음해 주세요.") from None
        raise TranscriptionError(502, "TRANSCRIPTION_FAILED", "음성을 글로 바꾸지 못했어요. 다시 녹음해 주세요.") from None
    except (URLError, TimeoutError) as error:
        if isinstance(error, TimeoutError) or isinstance(getattr(error, "reason", None), TimeoutError):
            raise TranscriptionError(504, "TRANSCRIPTION_TIMEOUT", "음성 전사 시간이 초과됐어요. 짧게 다시 녹음해 주세요.") from None
        raise TranscriptionError(503, "TRANSCRIPTION_UNAVAILABLE", "음성 전사 서버에 연결하지 못했어요.") from None
    except (ValueError, OSError, HTTPProtocolError):
        raise TranscriptionError(502, "TRANSCRIPTION_FAILED", "음성 전사 응답을 확인하지 못했어요.") from None
