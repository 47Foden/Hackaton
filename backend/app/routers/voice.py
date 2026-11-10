from asyncio import timeout
import re
from threading import BoundedSemaphore
from typing import Annotated

import psycopg
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.routing import APIRoute
from starlette.requests import ClientDisconnect

from app.db.connection import DatabaseConfigurationError
from app.repositories.menus import CatalogReadError, list_menus
from app.schemas.voice import RestartRecommendation, MenuId, VoiceAudioResponse, VoiceInterpretResponse, VoiceStage
from app.services.voice.audio import (
    AUDIO_TOO_LARGE_MESSAGE, MAX_AUDIO_BYTES, SAMPLE_RATE_HZ, PreparedVoiceAudio, VoiceAudioError, prepare_voice_audio,
)
from app.services.voice.interpretation import interpret_transcript
from app.services.voice.options import extract_options
from app.schemas.menus import Temperature
from app.services.voice.transcription import TranscriptionError, transcribe_voice
from app.schemas.voice import DirectRecommendation, SetOptions
from app.services.llm_direct import recommend as llm_recommend
from app.services.llm_direct import DirectError

MAX_MULTIPART_BYTES = MAX_AUDIO_BYTES + 16 * 1024
UPLOAD_TIMEOUT_SECONDS = 5
audio_slots = BoundedSemaphore(2)


class VoiceUploadRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()

        async def receive_audio(request: Request):
            if not audio_slots.acquire(blocking=False):
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
                audio_slots.release()

        return receive_audio


router = APIRouter(prefix="/api/voice", tags=["voice"], route_class=VoiceUploadRoute)


def _prepare_upload(audio: UploadFile) -> tuple[PreparedVoiceAudio, int]:
    data = audio.file.read(MAX_AUDIO_BYTES + 1)
    mime_type = audio.content_type or ""
    try:
        prepared = prepare_voice_audio(data, audio.filename or "", mime_type)
    except VoiceAudioError as error:
        raise HTTPException(error.status, detail={"code": error.code, "message": str(error)}) from None
    return prepared, len(data)


@router.post("/audio", response_model=VoiceAudioResponse)
def inspect_audio(audio: Annotated[UploadFile, File()]) -> VoiceAudioResponse:
    prepared, size_bytes = _prepare_upload(audio)
    return VoiceAudioResponse(
        mime_type=audio.content_type or "",
        container="webm",
        codec="opus",
        duration_seconds=prepared.duration_seconds,
        size_bytes=size_bytes,
        source_sample_rate_hz=prepared.source_sample_rate_hz,
        source_channels=prepared.source_channels,
        sample_rate_hz=SAMPLE_RATE_HZ,
        channels=1,
    )


def _invalid_context() -> HTTPException:
    return HTTPException(422, detail={
        "code": "INVALID_VOICE_CONTEXT", "message": "현재 주문 단계의 메뉴와 후보를 확인해 주세요.",
    })


@router.post("/interpret", response_model=VoiceInterpretResponse, response_model_exclude_none=True)
def interpret_audio(
    audio: Annotated[UploadFile, File()],
    stage: Annotated[VoiceStage, Form()],
    selected_menu_id: Annotated[MenuId | None, Form()] = None,
    candidate_menu_ids: Annotated[list[MenuId] | None, Form()] = None,
    selected_temperature: Annotated[Temperature | None, Form()] = None,
) -> VoiceInterpretResponse:
    candidates = tuple(candidate_menu_ids or ())
    requires_selection = stage in {"temperature", "customization", "service_type"}
    if ((requires_selection and selected_menu_id is None)
            or (not requires_selection and stage != 'menu_confirmation' and selected_menu_id is not None)
            or (stage == 'customization' and selected_temperature is None)
            or (stage == "recommendations") != bool(candidates)
            or len(set(candidates)) != len(candidates)):
        raise _invalid_context()
    if selected_temperature is not None and selected_menu_id is None:
        raise _invalid_context()

    try:
        menus = {menu["menu_id"]: menu for menu in list_menus()}
    except (psycopg.Error, DatabaseConfigurationError, CatalogReadError):
        raise HTTPException(503, detail={
            "code": "CATALOG_UNAVAILABLE", "message": "메뉴를 불러오지 못했어요. 잠시 후 다시 시도해 주세요.",
        }) from None
    if len(candidates) > len(menus):
        raise _invalid_context()
    if (selected_menu_id is not None and selected_menu_id not in menus) or any(menu_id not in menus for menu_id in candidates):
        raise _invalid_context()
    if selected_temperature is not None and selected_temperature not in menus[selected_menu_id]['available_temperatures']:
        raise _invalid_context()

    prepared, _ = _prepare_upload(audio)
    try:
        transcript = transcribe_voice(prepared.pcm_s16le)
    except TranscriptionError as error:
        raise HTTPException(error.status, detail={"code": error.code, "message": str(error)}) from None

    action = interpret_transcript(transcript, stage, menus, selected_menu_id=selected_menu_id, candidate_menu_ids=candidates)
    option_menu = menus.get(action.menu_id) if action.type == 'select_menu' else menus.get(selected_menu_id or '')
    option_transcript = re.sub(r'^\s*(?:네|예|맞아요)[,\s]+', '', transcript) if stage == 'menu_confirmation' else transcript
    recognized = extract_options(option_transcript, menu=option_menu, temperature=selected_temperature)
    if stage == 'customization' and option_menu and option_menu['is_available'] and recognized and recognized.customization:
        action = SetOptions(option_ids=recognized.customization.option_ids)
    if stage in {"menu", "recommendations"} and any(word in transcript.replace(" ", "") for word in ("재추천", "다시추천", "다른추천")):
        action = RestartRecommendation()
        recognized = None
    elif stage in {"menu", "recommendations"} and (action.type == "retry" and action.reason == "UNRECOGNIZED"):
        try:
            result = llm_recommend(transcript, list(menus.values()))['result']
            action = DirectRecommendation(**{k: result[k] for k in ('status', 'recommendations', 'questions', 'missing_information')})
            # A suggested temperature is not user intent. Validate both the
            # actual catalogue and any explicitly requested temperature.
            if any(r.menu_id not in menus or not menus[r.menu_id]['is_available']
                   or r.temperature not in menus[r.menu_id]['available_temperatures']
                   or (recognized and recognized.temperature and r.temperature != recognized.temperature)
                   for r in action.recommendations):
                raise DirectError('INELIGIBLE_OPTION')
        except DirectError:
            raise HTTPException(502, detail={'code': 'LLM_RECOMMENDATION_FAILED',
                'message': '메뉴 추천을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.'}) from None
        except (ValueError, OSError, KeyError):
            raise HTTPException(503, detail={'code': 'LLM_EVIDENCE_NOT_READY',
                'message': '현재 메뉴와 LLM 근거 자료의 연결을 확인해 주세요.'}) from None
    return VoiceInterpretResponse(transcript=transcript, action=action, recognized_options=recognized)
