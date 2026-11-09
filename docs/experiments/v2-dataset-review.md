# v2 새 발화 데이터셋과 무료 점검

`common/experiments/llm_direct/v2_accuracy_cases.json`은 기존 다섯 발화와 별도의 개발용 발화 10개다. 새 표현을 보며 조건 검증을 고쳤으므로 독립된 최종 평가셋/홀드아웃으로 주장하지 않는다. 향후에는 다른 사람이 작성한 새 발화로 같은 검사를 실행해야 한다.

발화 범위: 한글 예산 상한, 커피 거절, 우유 거절, 제외하지 말라는 부정, 숫자 카페인 0mg, 단맛 잔류, 떫음/건조감, 실제 목록에 없는 메뉴, 가격 충돌, 입력 속 지시문 주입.

각 항목에는 `evaluation`이 있다. `hard_constraints`는 실제 메뉴 가격·온도·판매 여부·카테고리·확인된 성분/카페인과 비교하는 별도 검사 기준이다. `preferred_actions`와 `review_note`는 적절한 질문/자료 보류/추천인지 사람이 검토할 기준이며 단일 정답이나 주관적 적합성 점수가 아니다. 이 항목들은 LLM 요청에 넣지 않고 결과 점검에서만 읽는다.

`evaluate_recommendations_v2.py`는 서버의 자연어 조건 해석 결과에 기대지 않고 데이터셋의 조건 주석으로 다시 검사한다. 서버가 거부한 원본 응답과 사용자에게 반환된 정상 응답을 구별한다. mock 결과는 `not_scored_mock`으로 두며 정확도 점수를 만들지 않는다. 서버 질문 응답도 모델 품질로 평가하지 않는다. 기존 추천은 원래 함수 결과를 보존하며 별도 조건 검사와 같은 평가를 받았다고 간주하지 않는다.

## 확인하고 수정한 문제

- 기존 v2 조건 해석이 “커피는 안 마셔요”, “우유는 안 돼요”를 놓칠 수 있었다. 명시적인 거절 형태를 보완했다.
- “커피를 제외하지 마세요”를 커피 제외로 해석할 수 있었다. 해당 부정 형태를 구분했다.
- “삼천 원을 넘기지 않는”과 숫자 “카페인 0mg” 표현을 보완했다.
- 전부 제한된 규칙의 보완이다. 복합 부정·인용·말 바꾸기를 완전히 해결했다고 주장하지 않는다. LLM 후보 선택 경로는 그대로다.

## 아직 남은 문제

1. `fit=general`과 올바른 사실 ID만으로도 추천이 통과할 수 있다. 사실 연결 통과는 사용자 의도/취향의 충족 보장이 아니다. 이 부분은 이번 실제 API 미실행으로 평가하지 않았다.
2. 감각 태그는 assistant의 보조 해석표다. 실제 관능 정답이 없으며 스스로 만든 표를 정답으로 채점하면 평가가 순환한다.
3. LLM 질문의 구체성·도움 여부는 자동 검증하지 못한다. 질문 후 답변을 기억하는 대화 상태도 아직 없다.
4. 설명이 없는 메뉴와 milk=false 미확인 자료 때문에 적절한 보류가 많을 수 있다. 보류가 늘어난 것과 추천 품질이 좋아진 것은 다르다.
5. 긴 입력, 실제 API의 응답 형식 수용, 지연·출력 잘림·반복 일관성은 새 데이터셋의 실제 호출로 확인해야 한다. 현재 무료 검증만으로 판단하지 않는다.

## 무료 재현

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -B -m unittest discover -s backend/tests -p test_v2_accuracy_dataset.py -v
python -B -m app.experiments.compare_recommendations_v2 --v1-report docs/experiments/2026-11-09-first-live/results.json --cases common/experiments/llm_direct/v2_accuracy_cases.json --mode mock --output-dir work/v2-new-cases-mock
```

키 파일을 읽거나 실제 API를 호출하지 않는다. v1 실제 DB 스냅샷을 그대로 사용하며 현재 판매 상태는 별도 확인해야 한다. 기존 결과는 덮어쓰지 않는다. 실제 호출·commit·push는 이번 무료 검증 범위가 아니다.
