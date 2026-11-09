# v2 메뉴 근거 재조사 (2026-11-09)

실제 메뉴 자료와 감각 추론을 구분해 미확인을 줄였다. 원래 `menu_evidence.json`과 `sensory_annotations_v2.json`, v1 결과는 덮어쓰지 않는다. 검색 자료와 추론을 독립 평가의 정답으로 간주하지 않는다.

## 반영 파일

- `common/experiments/llm_direct/menu_evidence_researched_v2.json`: 공식 페이지/실제 매장 상품 설명으로 보완한 사실 스냅샷. 기존 네 필드 구조 유지.
- `common/experiments/llm_direct/sensory_annotations_researched_v2.json`: 해당 근거 해시에 연결한 추론표. 빈 태그 8칸을 inferred로 보완했다.
- `common/experiments/llm_direct/research_changes_v2.json`: 사실 기록 9개의 추가·수정 및 태그 변경 전후와 남은 미확인 항목.

v2 CLI 기본 evidence는 조사본이다. `--evidence common/experiments/llm_direct/menu_evidence.json`을 지정하면 원래 자료로 재현한다. 태그 로더는 근거 해시가 정확히 일치하는 표만 사용한다. 직접 경로로 지정한 표가 다르면 자동 대체하지 않고 거부한다. 기존 v1 모듈/CLI의 기본 자료는 변경하지 않았다.

## 확인한 자료와 적용 범위

| 자료 | 확인한 것 | 적용 한계 |
|---|---|---|
| [공식 녹차라떼 HOT](https://www.mega-mgccoffee.com/menu/menu.php?category=6&menu_category1=1&menu_category2=1&page=1) | 녹차·우유·부드러움 설명, 우유 표기, 기본 당류 36.6g/591mL와 전환 원료 42.1g | 카페인은 기존 57.0mg/변경 82.9mg 병기. 실제 매장 원료 미확인으로 단일 수치 미확정 |
| [공식 녹차라떼 COLD](https://www.mega-mgccoffee.com/menu/menu.php?category=6&menu_category1=1&menu_category2=1&page=2) | 기본 당류 40.7g/591mL와 전환 원료 45.1g | 카페인 72.5mg/94.2mg 병기 상태를 유지. HOT 수치와 혼용하지 않음 |
| [정자엠코점 상품 목록](https://app.passorder.co.kr/normal/5c94c944-e062-4b61-b5b5-a89104f26d0f/menus) | 아이스 아메리카노의 에스프레소+물, 부드러움·바디감 상품 설명 | 브랜드 공식 영양표가 아니다. HOT 카페인 수치나 무우유 여부를 가져오지 않음. 이벤트 가격은 반영하지 않음 |
| [공식 레몬에이드](https://www.mega-mgccoffee.com/menu/menu.php?category=3&menu_category1=1&menu_category2=1&page=1) | 레몬 산미·탄산과 당류 53.6g/710mL | 단맛 가능성 추론에만 사용. 뒷맛·끈적함·저당 여부 확정 금지 |
| [공식 레몬차 HOT](https://www.mega-mgccoffee.com/menu/menu.php?category=2&menu_category1=1&menu_category2=1&page=1) / [COLD](https://www.mega-mgccoffee.com/menu/menu.php?category=2&menu_category1=1&menu_category2=1&page=2) | 각 온도 당류 59.3g/591mL, 71.1g/710mL | 실제 레몬티 별칭의 레시피 동일성 확인으로 확장하지 않음 |

검색으로 찾은 일반 떫음 연구([2024년 초록](https://pubmed.ncbi.nlm.nih.gov/38569410/), [구강 건조감 연구 초록](https://www.sciencedirect.com/science/article/pii/S0031938407004970))는 특정 매장 완제품 실험이 아니다. 이 일반 기전만으로 현재 메뉴의 실제 떫음/건조감이나 단맛 잔류를 채우지 않았다. 원문 접근이 제한된 자료는 검색에서 제공된 초록 범위로만 참고했다.

## 추론으로 채운 내용

- 아이스 아메리카노: 상품 설명의 바디감에서 묵직한 인상 가능성. 실제 텁텁함은 미확인.
- 녹차라떼 HOT: 확인한 우유·부드러움 설명에서 질감/묵직함 후보. 실제 떫음은 미확인.
- 레몬차 HOT/COLD, 레몬에이드 COLD, 녹차라떼 HOT/COLD: 해당 온도 당류 표기에서 단맛 가능성. 감각 강도나 뒷맛에 대한 정답이 아님.

모든 새 감각 태그는 inferred다. 추천 근거로 선택하면 관련 사실 ID와 함께 인용해야 하고 사용자 설명에도 실측이 아닌 추론임이 표시된다. 숫자 영양표가 들어갔지만 점수/가중치/정렬에는 사용하지 않는다. 후보와 순서는 여전히 LLM이 선택한다.

## 남긴 미확인

레몬티 별칭의 레시피 동일성, 명시적인 우유 미포함 자료, 녹차라떼의 실제 적용 원료와 단일 카페인 값, 아이스 아메리카노의 해당 온도 공식 영양값, 메뉴별 떫음·단맛 잔류의 실측 자료는 확인하지 못했다. 알레르기 공란을 없음으로 바꾸지 않았다. 가격·현재 판매 여부는 이 조사로 수정하지 않는다.

웹 자료는 접근 시점의 표시/검색 스냅샷이며 현재 매장 상태를 보장하지 않는다. 새 근거로 실제 API 비교를 할 때는 이전 v2와 자료 버전이 달라졌음을 기록한다. 이번 작업에서 실제 API 호출·키 파일 접근·commit·push는 하지 않는다.
