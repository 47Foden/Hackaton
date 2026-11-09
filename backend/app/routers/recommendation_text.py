"""Opt-in text inspection of the real recommenders. Never loads a key file."""
import json
import os
from threading import BoundedSemaphore
from time import perf_counter
from typing import Literal

import psycopg
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.connection import DatabaseConfigurationError
from app.repositories.menus import CatalogReadError, list_menus
from app.services.llm_direct import DirectError, openai_transport
from app.services.llm_direct_v3 import recommend as direct_recommend
from app.services.recommendation import recommend as existing_recommend
from app.services.sensory_tags import RESEARCHED_EVIDENCE

router = APIRouter(prefix='/api/experiments/recommend-text', tags=['text recommendation experiment'])
llm_slot = BoundedSemaphore(1)
DEFAULT_MODEL = 'gpt-5.4-mini-2026-03-17'


class TextRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    transcript: str = Field(min_length=1, max_length=4000)
    engine: Literal['existing', 'llm-v3'] = 'existing'
    paid_call_confirmed: bool = False

    @field_validator('transcript')
    @classmethod
    def nonblank(cls, text):
        if not text.strip():
            raise ValueError('빈 발화는 사용할 수 없습니다.')
        return text.strip()


def settings():
    return {'llm_enabled': os.environ.get('LLM_TEXT_EXPERIMENT_ENABLED') == '1',
            'api_key_configured': bool(os.environ.get('OPENAI_API_KEY')),
            'model': os.environ.get('LLM_TEXT_MODEL', DEFAULT_MODEL),
            'default_engine': 'existing', 'voice_engine': 'existing',
            'max_recommendations': 1, 'multi_turn_supported': False}


@router.get('')
def status():
    # Boolean availability only. Never returns credentials or environment contents.
    return settings()


def fail(status, code, message):
    return HTTPException(status, detail={'code': code, 'message': message})


@router.post('')
def recommend_text(body: TextRequest):
    config = settings()
    use_llm = body.engine == 'llm-v3'
    if use_llm:
        if not config['llm_enabled']:
            raise fail(403, 'LLM_TEXT_DISABLED', '서버에서 LLM 텍스트 시험을 켜지 않았어요.')
        if not body.paid_call_confirmed:
            raise fail(422, 'PAID_CALL_NOT_CONFIRMED', '유료 API 1회 호출 버튼으로 실행해 주세요.')
        if not config['api_key_configured']:
            raise fail(503, 'LLM_KEY_NOT_CONFIGURED', '서버에 API 키가 설정되지 않았어요. 키를 화면에 입력하지 마세요.')
        if not llm_slot.acquire(blocking=False):
            raise fail(503, 'LLM_TEXT_BUSY', '다른 LLM 요청을 처리 중이에요. 완료 후 다시 실행해 주세요.')
    start = perf_counter()
    try:
        try:
            menus = list_menus()
        except (psycopg.Error, DatabaseConfigurationError, CatalogReadError):
            raise fail(503, 'CATALOG_UNAVAILABLE', '현재 메뉴를 불러오지 못했어요.') from None
        if not use_llm:
            try:
                ids = existing_recommend(body.transcript, menus)
            except ValueError:
                raise fail(422, 'EXISTING_INPUT', '기존 방식이 이 발화의 추천 조건을 처리하지 못했어요.') from None
            except (KeyError, OSError):
                raise fail(503, 'DATASET_NOT_READY', '기존 추천 자료를 확인해 주세요.') from None
            by_id = {m['menu_id']: m for m in menus}
            if any(mid not in by_id or not by_id[mid]['is_available'] for mid in ids):
                raise fail(503, 'INVALID_EXISTING_RESULT', '기존 추천 결과의 판매 상태를 확인하지 못했어요.')
            result = {'status': 'recommend' if ids else 'insufficient_data',
                      'recommendations': [{'menu_id': mid, 'name': by_id[mid]['name'],
                                           'price_krw': by_id[mid]['price_krw'], 'temperature': None,
                                           'reason': '기존 CSV·규칙 추천 결과입니다. 온도와 주문 옵션은 다음 단계에서 확인하세요.'} for mid in ids],
                      'questions': [], 'missing_information': [] if ids else ['조건에 맞는 후보가 없어요.']}
            return {'engine': 'existing', 'transcript': body.transcript, 'result': result,
                    'latency_ms': round((perf_counter()-start)*1000, 3), 'usage': None,
                    'model': None, 'api_calls': 0, 'cost_usd_estimate': 0}
        try:
            evidence = json.loads(RESEARCHED_EVIDENCE.read_text(encoding='utf-8'))
            def send(payload):
                if config['model'].startswith('gpt-5.4-mini'):
                    payload = {**payload, 'reasoning': {'effort': 'none'}}
                return openai_transport(payload)
            response = direct_recommend(body.transcript, menus, evidence, config['model'], send)
        except DirectError as error:
            # Known safe machine code only; never return raw provider bodies or headers.
            code = str(error)
            if not code.replace('_', '').isalnum() or not code.isupper():
                code = 'LLM_RESPONSE_REJECTED'
            raise fail(502, code, 'LLM이 응답하지 못했거나 서버 검증을 통과하지 못했어요. 자동 재시도는 하지 않았어요. 실패 호출도 과금될 수 있어요.') from None
        except (ValueError, OSError, KeyError):
            raise fail(503, 'LLM_EVIDENCE_NOT_READY', '실제 메뉴와 LLM 근거 자료의 연결을 확인해 주세요.') from None
        by_id = {m['menu_id']: m for m in menus}
        result = response['result']
        result['recommendations'] = [{**r, 'name': by_id[r['menu_id']]['name'],
                                      'price_krw': by_id[r['menu_id']]['price_krw']} for r in result['recommendations']]
        usage = response['usage']
        amount = None
        if config['model'] == DEFAULT_MODEL and usage:
            cached = usage.get('input_tokens_details', {}).get('cached_tokens', 0)
            amount = ((usage['input_tokens']-cached)*0.75 + cached*0.075 + usage['output_tokens']*4.5)/1_000_000
        return {'engine': 'llm-v3', 'transcript': body.transcript, 'result': result,
                'model': response['model'], 'usage': usage, 'cost_usd_estimate': amount,
                'api_calls': 1, 'latency_ms': round((perf_counter()-start)*1000, 3)}
    finally:
        if use_llm:
            llm_slot.release()
