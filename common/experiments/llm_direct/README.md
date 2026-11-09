# 직접 추천용 메뉴 근거 자료

`menu_evidence.json`은 기존 메뉴/가격/CSV를 덮어쓰지 않는 별도 자료다. 2026-11-09에 열어 확인한 메가MGC커피 공식 페이지의 설명을 짧게 요약하고 온도별 카페인/명시된 알레르기 성분을 기록했다. 원문 전체를 복제하지 않는다. 실제 매장의 레시피/옵션/판매 여부를 보장하지 않는다.

각 필드는 `verified` 또는 `unknown`이다. 미확인에는 value/source/checked_date를 모두 null로 둔다. verified에는 사실값, HTTPS 출처, 확인일이 필요하다. 이름만 보고 우유·카페인을 추정하지 않는다. 알레르기 공란은 '없음'으로 바꾸지 않는다. '우유'가 명시된 경우만 포함 true로 기록했으며 무우유 false는 임의로 채우지 않았다.

HOT 근거는 HOT에만 적용하며 COLD로 복사하지 않는다. 저장소 레몬티 별칭과 공식 레몬차의 동일성, 녹차라떼와 유사 말차 상품의 동일성은 별도 확인한다. 공식 페이지는 동적으로 바뀌므로 링크의 페이지 번호가 이후 달라질 수 있다. 이름/온도/기본 1회 제공량을 다시 확인한 뒤 갱신한다.

자료 추가 방법:

1. 상품 이름과 HOT/COLD가 정확히 맞는 공식 상품 설명/성분표를 연다.
2. 확인한 필드만 value에 기록하고 source에 URL, checked_date에 확인일을 적는다.
3. description은 짧은 사실 요약이다. '끈적이지 않다', '잠을 방해하지 않는다'처럼 자료에 없는 결론은 만들지 않는다.
4. caffeine_mg는 기본 1회 제공량 mg이며 샷/사이즈 변경에는 적용하지 않는다. 0 표기가 수면 효과 보장은 아니다.
5. milk는 성분/레시피의 명시적 포함/미포함 근거가 있어야 한다. 알레르기 미표기만으로 false를 쓰지 않는다. allergens는 공식 표기에 나열된 성분만 기록하며 교차접촉 안전성은 별도다.
6. 전용 점검 명령을 실행해 오타·출처 누락·ID/온도 불일치를 확인한다. 스키마 통과가 자료의 진실성을 입증하는 것은 아니다.

기존 가격 출처와 온도 정의는 common/README.md를 따른다. 특히 에스프레소 가격은 쿠폰 자료라 매장 확인이 필요하다. 이 파일은 실시간 판매 상태를 포함하지 않는다.

루트 PowerShell에서 API 없이 준비:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -B -m app.experiments.menu_evidence --catalog-fixture --output-dir work/offline-preparation
```

생성 파일: `readiness.ko.md`/`readiness.json`(누락 현황), `verified-facts.json`(기존 --facts 호환), `menus.json`(실험용 메뉴), `requests-preview.json`(전송하지 않은 실제 요청 형식), `cases-unassisted.json`(조건 주석 없는 비교 입력). `--catalog-fixture`의 판매 여부는 합성 True이며 실제 판매 상태가 아니다. 실제 DB에서 저장한 `/api/menus` JSON이 있으면 `--menus work/menus.json`으로 교체한다.

`--response work/manual-response.json --case-id budget_no_coffee`로 손으로 작성한 구조화 응답을 검증할 수도 있다. 예: `{"status":"clarify","recommendations":[],"questions":["커피 종류를 모두 제외할까요?"],"missing_information":[]}`. 이 응답의 합격 여부는 서버 검증 결과이며 LLM 품질이 아니다. 잘못된 응답은 readiness.json의 manual_response_check에 기록한다.

무료 비교 파이프라인:

```powershell
python -B -m app.experiments.compare_recommendations --mode mock --menus work/offline-preparation/menus.json --repeat 3 --output work/offline-preparation/comparison-mock.json
```

기존 unverified_exclusions 검증은 설명을 추가해도 자동 해제되지 않는다. 우유/카페인 조건을 서버에서 보증하려면 공식 사실을 정형 조건과 연결하는 별도 검증 설계가 필요하다. 지금은 해당 조건에 확인 질문/자료 부족 응답을 허용하는 보수적 실험이다.
