import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic

MAX_AUDIO_BYTES = 2 * 1024 * 1024
MAX_AUDIO_SECONDS = 30
AUDIO_PREPARATION_TIMEOUT_SECONDS = 5
AUDIO_TOO_LARGE_MESSAGE = '녹음 파일이 2 MiB를 넘었어요. 짧게 다시 녹음해 주세요.'
SAMPLE_RATE_HZ = 16_000
PCM_SAMPLE_BYTES = 2


class VoiceAudioError(Exception):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass(frozen=True)
class PreparedVoiceAudio:
    pcm_s16le: bytes
    source_sample_rate_hz: int
    source_channels: int

    @property
    def duration_seconds(self) -> float:
        return len(self.pcm_s16le) / (PCM_SAMPLE_BYTES * SAMPLE_RATE_HZ)


def _ebml_integer(data: bytes, offset: int, *, keep_marker: bool = False) -> tuple[int, int]:
    if offset >= len(data) or data[offset] == 0:
        raise ValueError("Invalid EBML integer")
    width = 9 - data[offset].bit_length()
    end = offset + width
    if end > len(data):
        raise ValueError("Incomplete EBML integer")
    value = int.from_bytes(data[offset:end], "big")
    return (value if keep_marker else value & ((1 << (7 * width)) - 1)), end


def _has_webm_header(data: bytes) -> bool:
    # FFprobe uses one demuxer name for both Matroska and WebM.
    if not data.startswith(b"\x1a\x45\xdf\xa3"):
        return False
    header = data[:4096]
    try:
        size, offset = _ebml_integer(header, 4)
        end = offset + size
        if end > len(header):
            return False
        doc_types = []
        while offset < end:
            field, offset = _ebml_integer(header, offset, keep_marker=True)
            length, offset = _ebml_integer(header, offset)
            if offset + length > end:
                return False
            if field == 0x4282:
                doc_types.append(header[offset:offset + length])
            offset += length
        return doc_types == [b"webm"]
    except ValueError:
        return False


def _run_audio_tool(*args: str, deadline: float) -> bytes:
    try:
        remaining = deadline - monotonic()
        if remaining <= 0:
            raise subprocess.TimeoutExpired(args, AUDIO_PREPARATION_TIMEOUT_SECONDS)
        return subprocess.run(args, capture_output=True, check=True, timeout=remaining).stdout
    except FileNotFoundError:
        raise VoiceAudioError(503, "AUDIO_TOOLS_UNAVAILABLE", "녹음 파일을 처리할 수 없어요.") from None
    except subprocess.TimeoutExpired:
        raise VoiceAudioError(504, "AUDIO_TIMEOUT", "녹음 파일 확인 시간이 초과됐어요. 짧게 다시 녹음해 주세요.") from None
    except subprocess.CalledProcessError:
        raise VoiceAudioError(422, "INVALID_AUDIO", "녹음 파일을 읽을 수 없어요.") from None


def prepare_voice_audio(data: bytes, filename: str, mime_type: str) -> PreparedVoiceAudio:
    if len(data) > MAX_AUDIO_BYTES:
        raise VoiceAudioError(413, "AUDIO_TOO_LARGE", AUDIO_TOO_LARGE_MESSAGE)
    if not data:
        raise VoiceAudioError(422, "EMPTY_AUDIO", "녹음된 음성이 없어요.")
    mime = ";".join(part.strip() for part in mime_type.lower().split(";"))
    if Path(filename).suffix.lower() != ".webm" or mime not in {"audio/webm", "audio/webm;codecs=opus"}:
        raise VoiceAudioError(415, "UNSUPPORTED_AUDIO", "WebM/Opus 녹음 파일을 보내 주세요.")
    if not _has_webm_header(data):
        raise VoiceAudioError(415, "AUDIO_FORMAT_MISMATCH", "파일 이름과 실제 녹음 형식이 일치하지 않아요.")

    with TemporaryDirectory(prefix="kiosk-voice-") as temp:
        deadline = monotonic() + AUDIO_PREPARATION_TIMEOUT_SECONDS
        source = Path(temp) / "source.webm"
        source.write_bytes(data)
        probe = json.loads(_run_audio_tool(
            "ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe", "-of", "json",
            "-show_entries", "format=format_name:stream=codec_type,codec_name,sample_rate,channels",
            str(source), deadline=deadline,
        ))
        streams = probe.get("streams", [])
        formats = probe.get("format", {}).get("format_name", "").split(",")
        if ("webm" not in formats or len(streams) != 1
                or streams[0].get("codec_type") != "audio" or streams[0].get("codec_name") != "opus"):
            raise VoiceAudioError(415, "AUDIO_FORMAT_MISMATCH", "녹음에 WebM/Opus 오디오 트랙 하나가 필요해요.")
        stream = streams[0]
        if not stream.get("sample_rate") or not stream.get("channels"):
            raise VoiceAudioError(422, "INVALID_AUDIO", "녹음의 오디오 정보를 확인하지 못했어요.")

        # Chrome recordings can omit container duration. Decode one extra second to enforce the limit.
        pcm = _run_audio_tool(
            "ffmpeg", "-nostdin", "-v", "error", "-xerror", "-protocol_whitelist", "file,pipe",
            "-i", str(source), "-map", "0:a:0", "-t", str(MAX_AUDIO_SECONDS + 1),
            "-ac", "1", "-ar", str(SAMPLE_RATE_HZ), "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1",
            deadline=deadline,
        )

    result = PreparedVoiceAudio(pcm, int(stream["sample_rate"]), stream["channels"])
    if not pcm:
        raise VoiceAudioError(422, "EMPTY_AUDIO", "녹음된 음성이 없어요.")
    if result.duration_seconds > MAX_AUDIO_SECONDS:
        raise VoiceAudioError(413, "AUDIO_TOO_LONG", "녹음이 30초를 넘었어요. 30초 이내로 다시 녹음해 주세요.")
    return result
