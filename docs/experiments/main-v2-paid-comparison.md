# 현재 main 대 의미 해석 v2: 추가 비교 실행

목적: 이전 유료 비교의 기준은 769d2d9 기반 개선 코드였다. 이번에는 2026-11-12 확인한 실제 origin/main f6bbfcb와 semantic-direct-v2를 비교한다. 실험 파일 준비 및 무료 mock만 수행했으며 실제 유료 실행은 키 소유자에게 맡긴다.

## 사전 고정한 새 말투

| 유형 | 같은 발화로 양쪽 각각 1회 |
|---|---|
| 단순 제외 | 레몬 말고 딸기 계열로 골라줘 |
| 복합 제외 | 레몬하고 망고는 싫고 딸기 음료가 좋아요 |
| 이중 부정 | 레몬이 싫다는 건 아니에요. 마실 것 좀 추천해 주세요 |
| 일반 요청 | 딸기 맛 나는 걸로 골라주세요 |

평가용 예상 해석은 사람이 작성했고 모델 요청에 포함하지 않는다. 이전 8회 유료 평가와 정확히 같은 문장은 사용하지 않는다. 표현 4개 각 1회로 반복 일관성·전체 정확도를 입증하는 것은 아니다.

## 기준 코드 재현

`main_selector_snapshot`에 Git에서 추출한 main의 llm_direct/recommendation_conditions/taste_evidence 원본 3개를 고정했다. 원본 내용은 변경하지 않고 SHA-256(LF 정규화)을 manifest에 저장했다.

스냅샷 패키지 경로가 달라 원본 llm_direct가 import한 함수 네 개를 같은 main 출처의 함수로 연결한다. ROOT/DEFAULT_EVIDENCE 경로는 검증한 공유 자료 위치로 지정한다. 공용 catalog/menu_evidence/schema 및 메뉴 JSON은 main과 같은지 확인하고 다르면 실행을 거부한다. 작업 브랜치의 개선된 파서가 기준 코드에 섞이지 않는 것을 테스트했다. 함수 이름만 main으로 표시한 모의 기준이 아니다.

신규 측은 현재 실험 모듈 v2다. 두 방식의 소스·요청·데이터셋·메뉴·설명 해시 및 기준 main 커밋을 기록한다. 프롬프트/응답 스키마/후보 제한 차이는 의도한 비교 대상이다.

## 무료 점검

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path + ';' + (Resolve-Path backend/tests).Path
python -X utf8 -B -m unittest test_main_semantic_study test_semantic_paid_study -q
python -X utf8 -B -m app.evaluation.semantic_paid_study --mode plan --baseline-main --cases-file backend/app/evaluation/main_semantic_holdout.json --output-dir PATH_TO_PLAN
```

실제 키/환경 파일 없이 스냅샷 로딩·기준 보존·원본 main 오류 코드·요청 8개·양쪽 동일 모델/출력 상한·mock 경로를 검사한다.

## 키 소유자의 유료 실행

로컬 보조 명령 `outputs/semantic-direct/run-main-v2-live.cmd`는 별도 main-v2-live-study 폴더를 쓴다. 앞선 live-study 결과는 유지한다. RUN8 확인 뒤 기존 backend/.env의 키를 사용자 PC에서 읽는다. 키 값이나 전체 오류 본문을 출력/기록하지 않는다.

- 양쪽 모델: gpt-5.4-mini-2026-03-17.
- 기존 4회 + 신규 4회, 총 최대 8회. 자동 재시도 없음.
- 두 방식 최대 출력량 2048토큰, 요청 시작 간 최소 30초. 대기 시간은 API 응답시간에서 제외한다.
- 지난 실측 기준 약 $0.20 전후를 참고할 수 있으나 이번 비용은 미측정이다. 보수적 바이트 계획액은 별도로 표시하며 예상 청구액/강제 상한이 아니다.
- 공급자 오류가 나면 중단·미평가 처리한다. 같은 결과 폴더로 재개하면 이미 시도한 항목은 건너뛰고 미시작 항목만 실행한다. 과금 불명 항목도 자동 반복하지 않는다.
- 키 소유자가 직접 실행하기 전에는 API 호출하지 않는다. main 교체·웹/음성 연결·DB 변경·commit·push도 하지 않는다.

해석 일치(기존 Python / 신규 LLM), 제한된 후보 조건 검사, 원응답 계약 위반, 정규화 후 전달 가능 여부, 근거·시간·토큰·캐시 비용을 구분해 검토한다. 추천 성공만으로 원문 해석이 정확하다고 보지 않으며, 중복 제거 결과를 모델 생성 품질 향상으로 계산하지 않는다.
