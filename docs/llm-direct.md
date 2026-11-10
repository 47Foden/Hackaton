# 음성 전사와 LLM 직접 추천

현재 서비스는 `음성 녹음 → Whisper 전사 → 직접 메뉴명 선택 또는 LLM 추천 → 옵션 → 주문번호`로 동작한다.
추천 구현은 `backend/app/services/llm_direct.py` 하나다. 실험 v1/v2/v3 실행기, 11종 자료, CSV 추천·Pretuning 생성기는 제거했다. 이전 실험은 Git 이력에서 확인할 수 있다. 원격 실험 브랜치나 main은 이 정리로 변경하지 않는다.

## 설정과 실행

`backend/.env`에 서버 전용 OpenAI 키를 설정한다. 프론트에는 전달하지 않는다.

```dotenv
OPENAI_API_KEY=본인의_API키
LLM_RECOMMENDATION_MODEL=gpt-5.4-mini-2026-03-17
VOICE_TRANSCRIPTION_URL=http://host.docker.internal:8765/transcribe
```

모델은 해당 키로 접근 가능한 Responses·구조화 출력 지원 모델 ID로 변경할 수 있다. 자동 모델 대체는 없다. 기존 `RECOMMENDATION_ENGINE` 설정은 더 이상 사용하지 않으므로 제거한다. 옛 `common/experiments/`를 가리키는 `LLM_MENU_EVIDENCE_FILE` 설정도 제거한다. 기본 자료 경로는 `COMMON_DIR/menu_evidence.json`이며 Compose에서는 `/common/menu_evidence.json`이다.

```powershell
docker compose up -d --build --force-recreate backend frontend
```

DB 마이그레이션과 시드는 [DB 안내](../backend/app/db/README.md)를 따른다. DB 볼륨을 삭제할 필요는 없다.
RunPod Whisper와 SSH 터널은 별도로 실행해야 한다. GPU 사용 방식은 이 정리로 바뀌지 않는다.

## 추천 동작

- 메뉴 이름이 정확히 일치하면 LLM 호출 없이 메뉴를 선택한다.
- 메뉴·추천 단계의 나머지 의미 있는 전사 원문은 현재 DB의 45종 메뉴·가격·온도·판매 여부와 함께 LLM에 전달한다.
- LLM이 조건에 적합하다고 판단한 메뉴를 최대 6개 직접 선택한다. 개수를 지정하지 않으면 최대 6개까지 허용하고, “두 개만” 등 더 적은 추천 개수가 있으면 해당 개수를 우선한다. 되묻는 질문은 하지 않는다. 같은 메뉴의 HOT/COLD는 중복 반환하지 않는다. 서버는 실제 메뉴 ID, 판매·온도·가격·명시적 제외 조건과 근거 필드를 검증한다. 점수 순위나 다른 추천기로 대체하지 않는다.
- 추천 실패 시 자동 재시도 없이 오류를 안내한다. 추가 호출은 사용자가 다시 녹음할 때 발생한다. API 요금은 요청별로 발생한다.
- 적합한 메뉴의 사진·메뉴명·가격·제공 온도를 표시한다. 4개 이하는 바로 모두 표시하고, 5~6개면 4개 미리보기에서 전체보기 버튼으로 전부 확인한다. 메뉴를 선택하면 기존 옵션·주문 확정 흐름으로 이어진다. 주문 생성은 기존 주문 API만 수행한다.
- 사용자가 온도나 예산을 말하지 않으면 해당 조건을 제한하지 않는다. 예를 들어 “과일 음료 추천해줘”는 메뉴명·분류의 의미로 적합한 과일 음료를 최대 6개 고르며 온도를 묻지 않는다. 실제 온도 선택은 메뉴 선택 뒤 옵션 단계에서 받는다. 재추천은 초기 입력으로 돌아간다. 대화 기록·원래 조건과 답을 합쳐 말하라는 안내는 표시하거나 재생하지 않는다.

## 공식 맛 근거와 한계

`common/menu_evidence.json`에는 공식 사이트에서 공식명·온도·원본 이미지 URL을 확인한 45종·71개 온도별 기본 메뉴 설명이 들어 있다. 가격·카테고리는 기존 로컬 데이터와 현재 DB를 사용하고, 맛은 공식 설명을 사용한다. 음성 요청마다 웹을 다시 검색하지 않는다.

달달함·상큼함·과일 등 설명 근거를 확인하고, 맛 요청에는 description 근거를 필수로 받는다. 일반 아메리카노를 달달한 후보로 내는 오류를 방지한다. 설명이 모호한 메뉴는 보수적으로 누락될 수 있으며 실측 맛 점수나 개인의 체감 맛을 보장하지 않는다. 우유·카페인·알레르기 전용 자료는 여전히 unknown이다.

출처·캐시 갱신과 회귀 테스트의 범위는 [외부 맛 자료 안내](menu-taste-research.md)를 따른다.

## 검증

백엔드:

```bash
PYTHONPATH=backend:backend/tests backend/.venv/bin/python -m unittest discover -s backend/tests -v
```

PostgreSQL 통합 시험에는 `DATABASE_URL`, `COMMON_DIR`, `FRONTEND_PUBLIC_DIR` 환경변수가 필요하며 DB의 고유 시험 스키마를 사용한다. DB가 없는 환경은 `test_llm_direct test_voice_llm_integration test_voice_interpret test_voice_audio` 모듈만 실행한다. LLM 단위·API 시험은 mock transport로 유료 호출 없이 계약과 오류 처리를 확인한다. 프론트는 `npm --prefix frontend test`, `npm --prefix frontend run build`, `npm --prefix frontend run test:e2e`로 확인한다.

## 실제 음성 예시 활용

추천 요청에는 ZIP에서 실제 전사한 12개 예시의 조건 해석을 함께 전달한다. 8개 발화는 프롬프트에 넣지 않고 점검에 사용한다. 자료는 자동 전사 기반 검토 초안이며 가중치 학습이나 검증된 정답 데이터가 아니다. 금액·종류·제외·추천 개수와 실제 옵션을 서버에서도 검증한다. 데이터 검수와 20개 재실행 방법은 [음성 예시 평가 안내](evaluation/speech20.md)를 따른다.
