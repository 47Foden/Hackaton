from asyncio import timeout
from threading import BoundedSemaphore
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.routing import APIRoute
from starlette.requests import ClientDisconnect

from app.schemas.voice import VoiceAudioResponse
from app.services.voice.audio import (
    AUDIO_TOO_LARGE_MESSAGE, MAX_AUDIO_BYTES, SAMPLE_RATE_HZ, VoiceAudioError, prepare_voice_audio,
)

MAX_MULTIPART_BYTES = MAX_AUDIO_BYTES + 16 * 1024
UPLOAD_TIMEOUT_SECONDS = 5
audio_slot = BoundedSemaphore(1)


class VoiceUploadRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()

        async def receive_audio(request: Request):
            if not audio_slot.acquire(blocking=False):
                raise HTTPException(503, detail={
                    "code": "AUDIO_BUSY", "message": "다른 녹음을 처리 중이에요. 잠시 후 다시 녹음해 주세요.",
                })
            try:
                body = bytearray()
                try:
                    async with timeout(UPLOAD_TIMEOUT_SECONDS):
                        async for chunk in request.stream():
                            if len(body) + len(chunk) > MAX_MULTIPART_BYTES:
                                raise HTTPException(413, detail={
                                    "code": "AUDIO_TOO_LARGE", "message": AUDIO_TOO_LARGE_MESSAGE,
                                })
                            body.extend(chunk)
                except TimeoutError:
                    raise HTTPException(408, detail={
                        "code": "AUDIO_UPLOAD_TIMEOUT", "message": "녹음 전송 시간이 초과됐어요. 다시 녹음해 주세요.",
                    }) from None
                except ClientDisconnect:
                    raise HTTPException(400, detail="Audio upload disconnected") from None

                # Keep FastAPI's UploadFile parsing, but bound the body before it reaches the multipart parser.
                buffered: bytes | None = bytes(body)
                body.clear()

                async def replay_body():
                    nonlocal buffered
                    if buffered is None:
                        return await request.receive()
                    message = {"type": "http.request", "body": buffered, "more_body": False}
                    buffered = None
                    return message

                return await handle(Request(request.scope, receive=replay_body))
            finally:
                audio_slot.release()

        return receive_audio


router = APIRouter(prefix="/api/voice", tags=["voice"], route_class=VoiceUploadRoute)


@router.post("/audio", response_model=VoiceAudioResponse)
def inspect_audio(audio: Annotated[UploadFile, File()]) -> VoiceAudioResponse:
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    mime_type = audio.content_type or ""
    try:
        prepared = prepare_voice_audio(data, audio.filename or "", mime_type)
    except VoiceAudioError as error:
        raise HTTPException(error.status, detail={"code": error.code, "message": str(error)}) from None
    return VoiceAudioResponse(
        mime_type=mime_type,
        container="webm",
        codec="opus",
        duration_seconds=prepared.duration_seconds,
        size_bytes=len(data),
        source_sample_rate_hz=prepared.source_sample_rate_hz,
        source_channels=prepared.source_channels,
        sample_rate_hz=SAMPLE_RATE_HZ,
        channels=1,
    )
