# 최신 STT·45종 서비스와 LLM 직접 추천 통합 초안

## 코드 공유와 DB의 관계

개인 DB 파일이나 API 키를 팀원에게 보내는 작업이 아니다. 팀의 최신 서비스 코드와 우리 추천 코드를 같은 버전으로 맞춘 뒤, 각자의 DB에 저장소의 migration 코드를 적용하는 방식이다. 기존 메뉴 조회 실패는 11종 코드가 새 메뉴 분류를 거부하는 조건에서 재현됐다. 각 팀원 환경의 실제 오류 원인은 별도 확인이 필요하다.

## 이번 변경

- 8136908의 LLM 실험 코드를 보존하면서 origin/main의 baa4a2f 변경을 별도 integration/taejun-stt-llm 작업 공간에 통합했다. main이나 원래 실험 작업 공간은 변경하지 않았다.
- 최신 45종 메뉴·카테고리·옵션 API와 화면, STT의 75초 전사 제한 및 busy/timeout 처리를 팀 코드 그대로 받아왔다.
- 음성의 추천 분기에서 RECOMMENDATION_ENGINE=llm-direct이면 STT 원문과 현재 DB 메뉴를 LLM에 전달한다. 기본 existing은 팀의 기존 추천 함수다. 자동 혼합·실패 시 fallback·재시도는 없다.
- 메뉴명을 직접 말해 선택하거나 주문 옵션을 처리하는 흐름은 기존 팀 로직을 유지한다. LLM은 추천이 필요한 분기에서만 호출한다.
- 직접 추천 결과의 후보 1개·온도·근거, 질문 또는 자료 부족 안내를 기존 음성 화면에 표시한다. 개발용 텍스트 입력 화면과 API를 다시 넣지 않았다.
- STT 75초, 오디오 처리와 LLM 45초를 합친 최대 구간을 고려해 브라우저 요청 제한은 140초로 맞췄다. 실제로 140초가 걸린다는 뜻이나 속도 개선 수치가 아니다.

## 메뉴 근거의 중요한 제한

현재 45종 이름·가격 출처와 이전 11종 공식 상품 레시피의 동일성이 확인되지 않았다. 따라서 `menu_evidence_45.json`의 설명·우유·카페인·알레르기는 모두 미확인으로 명시했다. 이름만 보고 새 설명이나 성분을 만들어 넣지 않았다. `official_name` 필드는 현행 이름을 담는 식별용 자리이며 외부 공식 제품 일치 검증을 뜻하지 않는다고 mapping_note에 표시했다.

이 상태에서 가격·온도·판매 등 확인 가능한 조건의 후보 선택은 가능하지만, 실제 맛·성분 취향은 질문/자료 부족이 많이 나올 수 있다. 과거 11종으로 측정한 v3 추천 성능이 새 45종에서도 유지된다고 주장하지 않는다. 실제 매장의 설명과 성분 자료를 확보한 후 출처와 날짜를 붙여 미확인을 보완해야 한다.

LLM은 현재 DB 가격을 사용하며 맛 CSV로 재정렬하지 않는다. 과거 CSV는 legacy-11 폴더에 바이트 그대로 보존했다. 팀의 45종 기본 추천은 아직 없는 continuous.csv를 요구하므로 자료 준비 전에는 안내 오류가 나도록 되어 있다. 이전 11종 점수표를 45종에 몰래 쓰지 않는다.

## 실행 단계

1. 이 통합 변경을 검토·커밋·공유한 뒤 팀원은 동일한 코드 버전을 받는다. 현재 초안은 아직 commit/push하지 않았다.
2. Docker Desktop을 켜고 원래 Compose와 각자의 개인용 프론트 override로 서비스를 갱신한다. 공용 Dockerfile/compose.yaml은 이 통합 때문에 수정하지 않았다.
3. 저장소의 `app.db.migrate`로 DB 구조 변경을 적용한다. seed는 팀 문서를 따르며, 과거에 사라진 메뉴 ID가 있다는 오류가 나오면 임의로 DB를 지우지 말고 메뉴 이관 정책을 정한다. 이번 작업에서 실제 DB migration/seed는 실행하지 않았다.
4. 먼저 GET /api/menus가 성공하고 메뉴 이름이 표시되는지 확인한다. 실제 DB에 현재 메뉴가 준비돼 있어야 한다.
5. Whisper 실행에는 모델 파일과 PyTorch 환경이 따로 필요하다. 이번 작업에서는 추가 다운로드나 실제 음성 인식을 실행하지 않았다. 팀원의 검증된 실행 환경·경로를 재사용하거나 별도 준비한다.
6. LLM을 사용하려면 개인용 외부 backend override의 environment에 RECOMMENDATION_ENGINE=llm-direct를 설정한다. 기본값은 existing이다. LLM_RECOMMENDATION_MODEL은 이전 실험과 같은 모델이 기본이며, OPENAI_API_KEY는 본인의 서버 환경에서만 설정한다. 키를 보내거나 프론트에 넣지 않는다.
7. LLM 설정이 켜진 상태의 추천 발화는 실제 유료 API를 한 번 호출한다. 무료 검증에서는 transport를 mock으로 바꿔 실제 API를 차단했다.

## 무료 확인

저장소 루트에서 PYTHONPATH에 backend와 backend/tests를 넣고 다음 테스트를 실행한다.

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path + ';' + (Resolve-Path backend/tests).Path
python -B -m unittest test_voice_llm_integration test_voice_interpret.InterpretationTests test_voice_interpret.TranscriptionTransportTests test_recommendation -v
```

현재 45종 통합용 테스트 10개는 전체 메뉴 API 계약, 현재 가격 사용, CSV 미사용, 미확인 자료 거부, 기존 기본값, STT→LLM 전달, 질문/자료 부족, 실패·fallback 없음, 직접 메뉴 선택을 확인한다. 음성 업로드 연결 테스트의 오디오 변환과 STT는 대체했으므로 실제 녹음·음성 인식 정확도 검증이 아니다. worker HTTP 테스트 역시 대체 전사기다.

v1/v2/v3의 과거 11종 데이터셋 실험과 그 테스트는 이력으로 보존했다. 현재 카탈로그가 45종으로 바뀌었으므로 옛 11종 전체 테스트가 같은 환경에서 그대로 통과한다는 보장은 하지 않는다. 과거 실행 재현은 8136908과 당시 스냅샷을 사용하고, 현행 통합 검증과 구분한다.

프론트는 npm ci 후 npm run build와 npm test로 확인한다. 실제 음성·실제 DB·유료 LLM의 통합 인수 시험은 아직 하지 않았다. 질문 뒤 다음 발화를 기억하는 다중 대화도 이번 통합에는 포함하지 않았다. 질문 안내에 원래 조건과 답을 합쳐 다시 말하도록 표시한다.
