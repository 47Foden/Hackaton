# v2 실험 공유: 보완한 점과 실제 결과

이 버전은 팀 검토용 실험 기록이다. 운영 웹·음성 추천은 기존 방식이며 배포 품질이나 v1 대비 개선을 입증한 버전이 아니다.

## 보완한 점

- 실제 메뉴와 온도별 확인 자료를 분리하고 미확인을 부재·0으로 처리하지 않도록 검증했다.
- 가격·온도·판매·제외 조건, 중복 ID, 근거와 태그의 메뉴/온도 연결을 검증한다. 기존 맛 점수로 다시 순위를 계산하지 않는다.
- 공식 설명과 assistant의 감각 해석 가설을 구분하고 자료 출처 및 변경 이력을 남겼다. 해석표는 정답지가 아니다.
- 전체 메뉴를 보고 LLM이 후보·질문을 직접 선택하는 full/llm 모드로 실행했다. guarded/eligible은 비교용이다.
- 개발 발화 10개, 별도 사실 평가, 요청 상한·자동 재시도 없음·중단 시 응답 기록을 추가했다.

## 실제 결과

키 소유자가 gpt-5.4-mini-2026-03-17로 10개 발화를 각 1회 실행했다. 추천 1건과 질문 1건이 서버 검증을 통과했고 8건은 거부됐다. 이는 추천 정확도 20%라는 의미가 아니다.

비용 추정 USD 0.115194, 평균 지연 2.656초, 입력 141166토큰·출력 2071토큰이다. v1과 발화 및 제공 정보가 달라 직접적인 우열 비교는 불가능하다. 반복 일관성과 독립적인 취향 적합성 평가는 미측정이다.

주요 실패는 긴 태그 ID 형식(4건), fit의 milk/caffeine 의미 및 근거 요건 혼동(3건), 미확인 우유 제외 처리(1건)였다. 형식만 고치면 모두 올바른 추천이 되는 것은 아니다. 자세한 내용은 [실패 분석](review.ko.md)을 참고한다.

## 파일과 무료 검증

- [읽기용 결과](results.ko.md), [구조화 결과 및 거부된 원래 응답](results.json), [테스트 기록](tests.txt)
- [설계·실행 방법](../v2-design.md), [개발 데이터셋 검토](../v2-dataset-review.md), [자료 조사 기록](../v2-menu-research.md)

저장소 루트 PowerShell에서 Python 3.11 이상으로 다음 명령을 실행한다. API 키·네트워크 호출은 필요 없다. 테스트 일부의 API call 로그는 mock이다.

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
$env:PYTHONPATH += ';' + (Resolve-Path backend/tests).Path
python -B -m unittest test_llm_direct test_llm_direct_v2 test_sensory_tags test_v2_accuracy_dataset test_researched_menu_evidence test_recorded_transport test_menu_evidence test_small_experiment test_recommendation -v
```

이번 검증은 직접 추천 v1/v2·감각표·데이터셋·조사 근거·기록 transport·메뉴 근거·소규모 실행·기존 추천의 9개 테스트 모듈, 76개 테스트를 실행했다. 저장소 전체 테스트는 별도 서버 의존성이 필요할 수 있다. mock 결과를 실제 추천 성능으로 제시하지 않는다.

## 다음 단계와 변경 경계

입력·응답 구조를 단순화한 소규모 실험을 다음 버전에서 검토한다. 축소 구현은 이 커밋에 포함하지 않는다. 기존 추천/Pretuning/CSV, 웹·Whisper, 공용 Dockerfile·compose는 변경하지 않았다.

공유 결과는 기존 저장 스냅샷을 사용하며 현재 판매 상태를 보장하지 않는다. 공유본의 로컬 경로만 치환했고 실패 결과를 수정하지 않았다. 키 파일·개인 CMD 실행 파일·인증 헤더·원시 API 시도 로그는 포함하지 않았다. 추가 유료 호출도 하지 않았다.
