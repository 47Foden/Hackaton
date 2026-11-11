# 원문 의미 해석과 후보 선택을 함께 맡기는 실험

브랜치: `experiment/taejun-llm-semantic-direct`. 기반: `769d2d9`.

## 변경 이유와 구조

기존 `llm_direct`도 원문을 LLM에 주지만, 그 전에 Python이 조건을 추출하고 후보/온도를 제한한다. 예를 들어 '레몬이랑 망고는 빼고 딸기'를 딸기+레몬 선호로 해석하면 LLM이 선택할 딸기 후보가 사라진다.

새 `llm_semantic_direct`는 원문을 파싱하지 않고 실제 메뉴 및 검증된 설명을 제공한다. LLM은 한 번의 응답에서 요청 요약, 구조화한 조건 및 근거 원문 인용, 직접 고른 메뉴 ID/온도/옵션/근거 필드를 반환한다. 서버가 고른 후보를 맛 점수로 다시 계산하거나 정렬하지 않는다. 기존 추천기로의 자동 fallback이나 해석 전용 추가 호출도 없다.

서버는 응답 형식, 원문 인용의 실제 포함 여부, ID·판매 여부·제공 온도, 해석 결과의 예산과 옵션 합산 가격, 실제 옵션 ID·선택 개수, 분류, 확인된 우유/카페인 값 및 근거 필드를 검사한다. 설명상 제외 맛 단어의 명시적 충돌도 선택 뒤 제한적으로 검사한다. 사용자 문장에 대한 기존 정규식 파서나 맛 필터는 호출하지 않는다.

## 원문 해석이 맞다는 보장은 아님

모델이 조건을 누락하거나 금액·제외 대상을 잘못 해석해도 서버가 그 의미 오류를 모두 알 수는 없다. 원문 인용의 포함 여부는 해석 정확성의 증거가 아니다. 좋아하는 맛에 대한 적합성도 기존 숫자표/키워드 점수로 대신 판단하지 않고 LLM에 맡기므로 실제 모델 평가가 필요하다.

설명의 제외 단어 충돌 검사는 문자열 포함을 보는 보수적 검사다. 설명 자체의 부정을 이해하지 못해 오탐할 수 있으며, 단어가 없다는 사실은 성분 미포함 증거가 아니다. 전체 성분·교차접촉 확인 자료가 없는 알레르기 제외 및 수면 영향 보장 등은 추천하지 못하도록 한다. 현재 레시피/성분 자료가 unknown인 메뉴에 대한 무우유·카페인 조건도 근거 없이는 통과하지 않는다.

재질문은 이번 범위에 추가하지 않았다. 질문 없이 필요한 자료/미해석 조건을 insufficient_data로 반환한다. 현재 주문 UI와 연결하지 않은 텍스트 실험이며 운영 경로의 계약은 유지한다.

## 비교 방법

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path + ';' + (Resolve-Path backend/tests).Path
python -X utf8 -B -m unittest test_semantic_direct test_semantic_comparison test_recommendation_input_guards test_llm_direct test_menu_research test_speech20.NaturalConditionTests test_voice_llm_integration -q
python -X utf8 -B -m app.evaluation.compare_semantic_direct --mode mock --output-dir PATH_TO_RESULTS
```

`--mode request`는 요청 구성만 확인한다. `--mode mock`은 사람이 작성한 고정 응답의 형식/검증 흐름까지 확인한다. `--mode live` 및 키 입력/환경 파일 로딩 기능은 제공하지 않는다. CLI는 외부 네트워크와 .env 읽기를 차단한다.

무료 검증 결과: 새 모듈/비교 테스트 17개와 기존 관련 회귀 42개, 합계 59개 통과. 직접 실행용 CMD로도 59개 통과 및 요청 8개/비교 보고서 생성 완료를 확인했다. 실제 API 호출은 0회다.

- 양쪽 모두 같은 모델 ID를 지정하고 동일한 45개 메뉴·가격·온도·옵션·설명을 사용한다. 판매 상태는 시험용으로 모두 True다. 실제 DB를 사용하지 않는다.
- 이전 방식은 기반 커밋에서 이어온 `llm_direct` 및 기존 조건 파서다. 새 방식은 별도 모듈이며 기존 파일을 수정하지 않았다.
- 단순 제외·복합 제외·이중 부정·일반 딸기 요청 4개에 대해 요청 8개를 JSON으로 저장한다. 요청 해시와 정보 차이, Python 해석, 허용 후보를 기록한다.
- 새 방식은 프롬프트/스키마/검증 역할이 바뀐다. 같은 메뉴 자료를 쓴다고 모든 제공 정보가 동일하다는 뜻은 아니다. prompts/guard_hints/후보 제한 차이가 비교 대상이다.
- 고정 응답은 `semantic_direct_cases.json`의 사람이 작성한 예상 조건과 후보를 사용한다. 실제 LLM 출력이나 학습 데이터, 실제 메뉴 설명의 대체 자료가 아니다.
- mock accepted/rejected 개수는 정확도나 성능 점수가 아니다. 실제 토큰·비용·시간·일관성은 미측정(null)이다. 코드가 올바른 모델 응답을 받아들일 수 있는지를 확인한다.

첫 구현은 무료 검증만 진행했다. 이후 사용자의 유료 비교 요청에 따라 별도 `semantic_paid_study` 실행기를 추가했다. 기존 무료 CLI에는 여전히 live 모드나 키 로딩이 없다. [유료 비교 실행 안내](semantic-direct-paid.md)의 실행기는 키 소유자의 대화형 터미널에서만 승인 후 사용할 수 있으며, 공급자 오류를 미평가로 분리하고 호출 간격 및 중단/재개를 관리한다. Codex가 실제 키 파일을 읽거나 유료 API를 호출한 것은 아니다.

## 추가 파일

- `backend/app/services/llm_semantic_direct.py`: 한 번의 해석+직접 선택 및 사후 사실 검증.
- `backend/app/evaluation/compare_semantic_direct.py`: 무료 비교 CLI와 보고서 생성.
- `backend/app/evaluation/semantic_direct_cases.json`: 사람 작성 예상 해석/응답 fixture 4개.
- `backend/tests/test_semantic_direct.py`: 새 모듈 구조·응답·사실·오류 처리 검사.
- `backend/tests/test_semantic_comparison.py`: 비교 CLI의 8개 mock 경로와 요청 전용 검사.
- 이 문서.

기존 공유 브랜치, 기존 추천 함수/자료, Whisper/웹 UI, 공용 Dockerfile/compose.yaml, .env는 변경하지 않는다. 이 실험은 별도 브랜치로 공유하며 main 병합은 별도 검토한다.

응답 스키마는 [OpenAI Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs)의 strict object 및 required 필드 구조를 따랐다. 무료 스키마 구조 검사는 실제 공급자의 스키마 수락 여부까지 입증하지는 않는다.
