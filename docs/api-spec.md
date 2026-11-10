# API 명세 — 기본 주문 흐름

## 1. 기준과 구현 상태

우선순위는 **common 데이터 → 이 문서와 DB 명세의 구체화된 계약 → [기본 주문 계획](plan/basic-order-flow.md)의 제안 → 이전 기획**이다. 사용자가 언급한 docs/basic-order-flow.md의 실제 경로는 docs/plan/basic-order-flow.md다.

GET /api/health, GET /api/menus, POST /api/orders, POST /api/voice/audio, POST /api/voice/interpret를 제공한다. 취향 추천은 음성 interpret 안에서 LLM을 직접 호출한다.

- 메뉴명·순서·분류: [order_catalog.json](../common/order_catalog.json).
- 가격: [menu_prices.json](../common/menu_prices.json). 메뉴 단위 정수 원화이며 온도별 가산금은 없다.
- 온도·이미지: [menu_images.json](../common/menu_images.json)의 HOT/COLD 키와 정적 자산 경로.
- 가격·이미지 근거: common/menu_price_sources.json, common/menu_image_sources.json. 가격은 전국 공통 공식 가격을 보장하지 않으며 에스프레소는 모바일쿠폰 가격이다.
- common은 카탈로그의 기준 원본, PostgreSQL은 이를 반영한 조회 데이터와 주문 기록의 원본이다. 요청마다 사이트를 수집하거나 가격을 추정하지 않는다.

## 2. 메뉴 ID와 데이터 매핑

현재 메뉴 45종의 고정 ID·이름·상위/하위 분류·옵션 프로필은 `common/order_catalog.json`에서 관리한다. 가격·제공 온도는 각 공통 JSON 및 현재 DB 조회를 사용한다. 메뉴 자료를 API 문서에 별도로 복제하지 않는다.

## 3. 공통 규칙

- 프론트 요청은 /api 상대 경로, JSON/UTF-8을 사용한다.
- 온도: HOT 또는 COLD. 공식 사이트 ICE는 수집 단계에서 COLD로 변환돼 있다.
- 이용 방식: DINE_IN 또는 TAKEOUT. 메뉴 1개·수량 1개, 결제 없음.
- 정수 가격, 불리언 상태를 사용한다. DB BIGINT 주문 ID는 JSON 문자열로 반환한다.
- created_at은 시간대가 있는 ISO 8601 문자열이며 서버는 UTC로 반환한다. 화면에서 한국 시간으로 표시할 수 있다.
- 알려지지 않은 주문 요청 필드, 필수 필드 누락, 자료형/enum 오류는 422다. 클라이언트가 전송한 가격·수량을 무시하고 성공시키지 않는다.
- 판매/노출 설정은 common에 없으므로 seed 기본값을 사용한다: is_available=true, display_order=MENUS 위치(1부터), is_featured는 common/menu_display.json의 simplified_menu_names 포함 여부로 설정한다. 현재 간편 목록은 4종이며 공식 인기/추천 순위가 아닌 프로젝트 표시 설정이다. 간편 목록이 비어 있으면 전체 메뉴를 표시한다.

## 4. GET /api/health — 구현됨

요청 본문 없음. 성공 200:

```json
{"status":"ok","database":"connected"}
```

현재 DB 오류는 503과 `{"detail":"Database unavailable"}`다. 이 API는 SELECT 1만 확인하며 메뉴 테이블·seed·이미지·음성 모델 준비 여부를 보장하지 않는다.

## 5. GET /api/menus — 구현됨

쿼리와 본문 없이 호출한다. 성공 200은 display_order 오름차순으로 정렬한 menus 배열을 반환한다. 동점은 menu_id COLLATE "C" 오름차순이다. 확장 seed는 메뉴 45종을 제공하며 판매 중지 메뉴도 is_available=false로 반환한다.

```json
{
  "menus": [
    {
      "menu_id": "peach_iced_tea",
      "name": "복숭아 아이스티",
      "categories": ["음료", "티"],
      "price_krw": 3000,
      "available_temperatures": ["COLD"],
      "variants": [
        {"temperature":"COLD","image_url":"/images/menus/peach-iced-tea-ice.jpg","option_groups":[]}
      ],
      "image_url": "/images/menus/peach-iced-tea-ice.jpg",
      "is_available": true,
      "display_order": 1,
      "is_featured": false
    }
  ]
}
```

| 필드 | 자료형 / 규칙 |
| --- | --- |
| menu_id, name | 필수 비어 있지 않은 문자열, `common/order_catalog.json`의 ID와 표시명 |
| categories | 필수 문자열 배열, 주문 카탈로그의 대분류와 하위 분류 |
| price_krw | 필수 0 이상 정수, 메뉴별 기본가 |
| available_temperatures | 필수 비어 있지 않은 배열. HOT, COLD 순서, 중복 없음 |
| variants | 각 제공 온도마다 정확히 한 객체. 온도 집합은 available_temperatures와 동일 |
| variants[].image_url | 필수 문자열, common의 해당 온도 경로 |
| variants[].option_groups | 해당 온도의 옵션 그룹 배열. 그룹은 `id`, `label`, `max_selections`, `choices`를 제공한다. 선택지는 `id`, `label`, `price_delta_krw`를 제공한다. 예시에서는 그룹을 생략했다. |
| image_url | 기본 카드 이미지. COLD가 있으면 COLD, 없으면 HOT 이미지 |
| is_available, is_featured | 필수 boolean |
| display_order | 필수 양의 정수 |

이미지는 프론트 origin의 frontend/public 아래에서 제공한다. 백엔드가 이미지 파일을 JSON으로 전송하지 않는다. 이미지 요청 실패 시 화면이 대체 이미지를 표시하되 메뉴 이름·가격은 유지한다. 계획의 nullable 이미지/온도별 가격 제안보다 현재 common을 우선하므로 응답 가격은 메뉴당 하나다.

온도가 한 가지면 프론트가 자동 선택하고, 두 가지면 온도 화면을 표시한다. 온도를 확정한 뒤 추가 옵션과 매장/포장을 선택한다. 자동 선택한 온도도 최종 확인과 주문 요청에 담는다.

메뉴가 없으면 200과 `{"menus":[]}`를 반환한다. DB 조회 실패/테이블 미적용과 카탈로그 응답 무결성 오류는 503 CATALOG_UNAVAILABLE이다. seed 검증은 빈 온도나 누락 이미지를 가진 메뉴의 게시를 막아야 한다.

## 6. POST /api/orders — 구현됨

프론트는 최종 확인 화면의 주문 확정 버튼을 눌렀을 때 요청한다. `request_id`는 하이픈을 포함한 UUID 문자열이다. 아래 네 필드가 필수다.

```json
{"request_id":"550e8400-e29b-41d4-a716-446655440000","menu_id":"peach_iced_tea","temperature":"COLD","service_type":"TAKEOUT"}
```

선택한 추가 옵션이 있으면 `option_ids` 배열을 함께 보낸다. 생략하면 빈 선택으로 처리한다. 서버는 한 트랜잭션에서 판매 여부, 온도, 옵션 소속과 선택 제한을 검증하고 DB 기본가와 추가금으로 합계를 계산한다. 수량은 1이며 커밋 확인 후 `201`을 반환한다. 같은 UUID와 같은 주문 내용은 옵션 순서와 관계없이 `200`과 기존 저장 결과를 반환한다.

```json
{
  "order_id":"1",
  "order_number":"1",
  "menu_id":"peach_iced_tea",
  "menu_name":"복숭아 아이스티",
  "temperature":"COLD",
  "service_type":"TAKEOUT",
  "quantity":1,
  "selected_options":[],
  "total_price_krw":3000,
  "created_at":"2026-11-07T00:00:00Z"
}
```

order_id와 order_number는 같은 orders.id를 문자열로 표현한다. menu_name, 금액, selected_options의 옵션명과 추가금은 주문 시점에 저장한다.

### 오류 계약

업무 오류 예시는 `{"detail":{"code":"INVALID_OPTION","message":"선택할 수 없는 온도 또는 추가 옵션입니다."}}`이다.

| HTTP | code | 조건 |
| --- | --- | --- |
| 404 | MENU_NOT_FOUND | 등록되지 않은 menu_id |
| 409 | MENU_UNAVAILABLE | 판매 중지 |
| 409 | IDEMPOTENCY_CONFLICT | 이미 저장된 UUID에 다른 메뉴, 온도, 이용 방식 또는 옵션이 들어옴 |
| 422 | INVALID_OPTION | 메뉴가 제공하지 않는 온도·옵션, 중복 옵션 또는 선택 제한 초과 |
| 503 | ORDER_STORAGE_UNAVAILABLE | DB 연결·저장·COMMIT 확인 실패 |
| 503 | CATALOG_UNAVAILABLE | 메뉴 조회 실패 (GET /menus) |

필수 값·타입·enum·추가 필드 오류는 FastAPI의 기본 422 detail 배열을 사용한다. 프론트는 detail 객체/배열/문자열을 구분하고 HTTP 상태도 확인한다. 예상하지 못한 서버 오류는 일반 500으로 처리하며 성공을 꾸며 반환하지 않는다.

### 중복 및 재시도

같은 UUID로 요청이 동시에 들어와도 주문은 한 건만 저장된다. 재전송 응답은 원래 주문의 번호, 이름, 가격, 생성 시각을 그대로 사용한다. 서로 다른 UUID는 별개의 주문으로 처리한다.

네트워크 단절, 타임아웃, `503`, `500`으로 접수 여부가 불명확하면 같은 주문 화면에서 사용자가 수동으로 재시도할 수 있다. 최초 UUID와 주문 내용을 그대로 보내므로 기존 저장 여부와 관계없이 주문은 최대 한 건이다. UUID 충돌은 직원 확인을 안내한다. 처음으로 이동하거나 페이지를 새로고침하면 주문 세션이 끝나며, 새 주문에는 새 UUID를 발급한다.

## 7. 후속 음성·추천 계약

### 7.1 `POST /api/voice/audio` — 오디오 검사·변환

multipart `audio` 필드로 `.webm` 파일을 받는다. 브라우저 MIME인 `audio/webm;codecs=opus`를 유지하며 `audio/webm`도 허용한다. 파일 이름, EBML DocType, `ffprobe`가 확인한 오디오 트랙 하나와 Opus 코덱이 일치해야 한다. 최대 크기는 2 MiB, 변환 후 재생 길이는 최대 30초다. FFmpeg로 16 kHz 모노 PCM16을 만들고, 입력에 길이 메타데이터가 없어도 PCM 샘플 수로 길이를 계산한다.

성공 `200`은 `mime_type`, `container`, `codec`, `duration_seconds`, `size_bytes`, `source_sample_rate_hz`, `source_channels`, `sample_rate_hz`, `channels`를 반환한다. 원본과 변환 데이터는 요청 종료 시 정리한다. Docker 백엔드 이미지가 FFmpeg와 ffprobe를 제공한다.

multipart 요청 전체는 오디오 제한에 헤더 여유 16 KiB를 더해 파싱 전에 제한한다. API 프로세스는 두 음성 경로를 합쳐 동시에 두 건까지 처리한다. 업로드 수신은 5초, ffprobe와 FFmpeg에는 합쳐서 5초, 브라우저 요청에는 15초를 적용한다. 초과 시 화면은 **다시 녹음**을 제공한다.

| HTTP | code | 조건 |
| --- | --- | --- |
| 408 | `AUDIO_UPLOAD_TIMEOUT` | 업로드 수신 타임아웃 |
| 413 | `AUDIO_TOO_LARGE`, `AUDIO_TOO_LONG` | 파일 크기 또는 변환된 길이 초과 |
| 415 | `UNSUPPORTED_AUDIO`, `AUDIO_FORMAT_MISMATCH` | 확장자·MIME 오류 또는 실제 컨테이너·코덱 불일치 |
| 422 | `EMPTY_AUDIO`, `INVALID_AUDIO` | 빈 파일 또는 디코딩 실패 |
| 503 | `AUDIO_BUSY`, `AUDIO_TOOLS_UNAVAILABLE` | 음성 요청 두 건을 처리 중이거나 FFmpeg 또는 ffprobe가 설치되지 않음 |
| 504 | `AUDIO_TIMEOUT` | 검사 또는 변환 도구 타임아웃 |

### 7.2 `POST /api/voice/interpret` — 전사와 주문 단계 해석

`multipart/form-data`로 전송한다. `audio`는 필수 파일이며 7.1의 WebM/Opus 형식과 크기·길이 제한을 적용한다. `stage`는 아래 값 중 하나인 필수 문자열이다. `candidate_menu_ids`는 같은 이름의 폼 필드를 후보 표시 순서대로 반복한다. JSON 배열, 쉼표 구분 문자열, `candidate_menu_ids[]` 키는 사용하지 않는다.

| `stage` | 필수 맥락 | 허용 응답 행동 |
| --- | --- | --- |
| `menu` | `audio`, `stage` | `select_menu`, `direct_recommendation`, `restart_recommendation`, `retry` |
| `temperature` | `audio`, `stage`, `selected_menu_id` | `set_temperature`, `retry` |
| `customization` | `audio`, `stage`, `selected_menu_id`, `selected_temperature` | `set_options`, `retry` |
| `service_type` | `audio`, `stage`, `selected_menu_id` | `set_service_type`, `retry` |
| `menu_confirmation` | `audio`, `stage`. `selected_menu_id`, `selected_temperature` 선택적 전달 | `confirm`, `retry` |
| `recommendations` | `audio`, `stage`, `candidate_menu_ids` 1개 이상, 현재 카탈로그 메뉴 수 이하 | `select_menu`, `direct_recommendation`, `restart_recommendation`, `retry` |
| `review` | `audio`, `stage` | `confirm`, `retry` |

메뉴 ID는 등록된 고정 ID를 사용한다. 단계에 해당하지 않는 맥락 필드와 중복 후보는 거부한다. 추천 화면의 메뉴 선택은 현재 후보 안에서만 가능하다. 판매 여부와 제공 온도는 DB 카탈로그를 기준으로 확인한다.

#### 음성 요청 목적 (`intent`)

`intent`는 선택적 multipart 문자열이며 `order` 또는 `recommend`를 사용한다. 화면 단계인 `stage`와 별개의 필드다. 명시적 목적은 `menu`, `recommendations` 단계에서만 허용하며, 나머지 단계에 전달하면 전사 전에 `422 INVALID_VOICE_CONTEXT`로 거부한다. 정의하지 않은 문자열은 FastAPI의 `422 detail` 검증 오류다.

| 요청 목적 | 처리 및 응답 |
| --- | --- |
| `order` | 등록 메뉴명 또는 현재 후보를 직접 선택한다. 해석하지 못하면 `retry/UNRECOGNIZED`이며 LLM 추천을 호출하지 않는다. 판매 중지·후보 밖 메뉴 검증도 유지한다. |
| `recommend` | 메뉴명이나 후보 순서를 말해도 바로 주문으로 선택하지 않고 추천 서비스를 호출한다. `direct_recommendation` 또는 기존 추천 오류를 반환하며 직접 주문으로 대체하지 않는다. |
| 필드 생략 | 기존 클라이언트 호환: 직접 메뉴 선택을 먼저 시도하고, 메뉴/추천 단계의 `UNRECOGNIZED`에서만 LLM 추천을 호출한다. |

빈 전사·공백·구두점만 있는 입력은 두 목적 모두 `retry/EMPTY_TRANSCRIPT`이며 LLM을 호출하지 않는다. “다시 추천”은 목적과 관계없이 `restart_recommendation`으로 먼저 처리하고 옵션을 초기화한다. 정상 추천 요청은 LLM을 한 번 호출하며 별도 자동 재시도나 주문 fallback이 없다.

`recognized_options`는 기존 계약을 유지한다. 명시적 `recommend`에서는 정확한 메뉴명이 있어도 메뉴가 선택된 것으로 보지 않으므로 커스터마이징 의도는 `pending`으로 보존한다(명시적 추가 옵션 없음은 `resolved`의 빈 선택). 사용자 발화 온도·이용 방식은 그대로 추출하고, 추천 모델의 후보 온도를 사용자 선택으로 복사하지 않는다. 실제 제공 온도 및 사용자 요청 온도와 충돌하는 추천은 기존 `502 LLM_RECOMMENDATION_FAILED`다.

예: 같은 “아이스 카페라떼 샷 추가 포장” 발화라도 `intent=order`는 `select_menu`와 검증된 샷 옵션을 반환하고, `intent=recommend`는 추천 결과와 아직 확정되지 않은 샷 의도를 반환한다. 이 단계의 서버 변경만으로 기존 프론트 버튼은 바뀌지 않는다. 후속 두 버튼 UI는 메뉴/추천 단계에서 목적을 명시적으로 전송한다.

```sh
curl -F 'audio=@recording.webm;type=audio/webm' -F 'stage=recommendations' \
  -F 'intent=order' \
  -F 'candidate_menu_ids=cafe_latte' -F 'candidate_menu_ids=green_tea_latte' \
  http://localhost:8000/api/voice/interpret
```

성공은 `200`과 `{ "transcript": "카페라떼 주세요.", "action": { "type": "select_menu", "menu_id": "cafe_latte" } }` 형식으로 반환한다. `action.type`별 필드는 다음과 같다.

| `type` | 필드 |
| --- | --- |
| `select_menu` | `menu_id` |
| `set_temperature` | `temperature` (`HOT` 또는 `COLD`) |
| `set_service_type` | `service_type` (`DINE_IN` 또는 `TAKEOUT`) |
| `set_options` | `option_ids`. 미해결 항목 여부는 `recognized_options.customization`에서 함께 확인 |
| `confirm` | 추가 필드 없음. 현재 메뉴 확인 또는 최종 주문 확인에 대한 명시적 동의 |
| `restart_recommendation` | 추가 필드 없음. 추천과 세션 옵션을 초기화하고 초기 음성 입력으로 이동 |
| `direct_recommendation` | LLM이 결정한 조건에 맞는 전체 후보 또는 자료 부족. |
| `retry` | `reason` (`EMPTY_TRANSCRIPT`, `UNRECOGNIZED`, `MENU_UNAVAILABLE`, `INVALID_OPTION`, `OUTSIDE_CANDIDATES`) |

빈 전사와 모호한 발화는 `200`의 `retry`로 안내한다. 단일 발화는 현재 단계의 행동 하나와 선택적 `recognized_options`를 반환한다. 추천은 별도 추천 API 없이 `direct_recommendation`으로 반환한다. 최종 주문 확인 화면의 버튼 또는 명시적 음성 확인 후에만 `POST /api/orders`를 호출한다. `interpret` 자체는 주문을 저장하지 않는다.

#### 발화에서 인식한 옵션 (`recognized_options`)

기존 `action`은 유지하고, 발화에 옵션이 포함되면 응답 최상위에 `recognized_options`를 추가한다. 옵션 미언급 시 필드 자체를 생략하며, 내부의 미인식 온도·이용 방식도 `null` 대신 생략한다. 추천 후보의 온도는 사용자 발화의 선택값으로 복사하지 않는다.

| 필드 | 의미 |
| --- | --- |
| `temperature` | `HOT` 또는 `COLD`. “시원한”, “차가운”, “아이스”는 `COLD` |
| `service_type` | `DINE_IN` 또는 `TAKEOUT` |
| `unresolved_fields` | 모호하거나 제공하지 않는 `temperature`/`service_type` 목록. 해당 필드는 기존 세션 값으로 조용히 확정하면 안 됨 |
| `customization.status` | `resolved`: 요청한 옵션 검증 완료, `pending`: 메뉴·온도 확정 대기, `needs_clarification`: 지원하지 않는 옵션·충돌·모호한 표현 있음 |
| `customization.option_ids` | 선택 메뉴·온도의 실제 옵션 그룹에서 검증한 ID 목록. `pending`에서는 빈 배열 |
| `customization.intents` | `{ expression, candidate_option_ids }` 목록. 메뉴·온도 확정 후 재검증할 발화 의도이며 후보 ID를 곧바로 주문에 사용하면 안 됨 |
| `customization.unresolved` | 추가 확인이 필요한 표현·사유 목록 |

예: “아이스 카페라떼 샷 추가하고 포장해 주세요”는 아래와 같이 반환한다.

```json
{
  "transcript": "아이스 카페라떼 샷 추가하고 포장해 주세요",
  "action": { "type": "select_menu", "menu_id": "cafe_latte" },
  "recognized_options": {
    "temperature": "COLD",
    "service_type": "TAKEOUT",
    "unresolved_fields": [],
    "customization": {
      "status": "resolved",
      "option_ids": ["shot:extra"],
      "intents": [{ "expression": "샷추가", "candidate_option_ids": ["shot:extra"] }],
      "unresolved": []
    }
  }
}
```

“샷 추가”만 말하고 메뉴 또는 온도가 아직 정해지지 않았으면 `pending`으로 보존한다. “추가 옵션 없이”는 `resolved`와 빈 `option_ids`이며 커스터마이징 미언급과 구분한다. “샷 추가하고 시럽도”는 유효한 샷 선택을 유지하고 시럽을 `unresolved`에 넣는다. “핫 말고 아이스”, “샷 추가 말고 연하게”는 명확한 정정을 반영하고, “핫이나 아이스”, 부정 표현, 중복 옵션, 그룹별 선택 개수 초과는 자동 확정하지 않는다.

추가 계약 예시(카페라떼가 HOT/COLD 및 샷 추가를 제공하는 경우):

| 발화와 단계 | 행동 및 인식 옵션 | 소비 규칙 |
| --- | --- | --- |
| 메뉴 단계 “카페라떼 주세요” | `select_menu`, `recognized_options` 생략 | 기존 옵션 선택 흐름 |
| 메뉴 단계 “카페라떼 샷 추가” | `select_menu`, 커스터마이징 `pending`, `option_ids: []`, 샷 의도 보존 | 온도 선택 후 의도를 검증하며 빈 배열을 “옵션 없음”으로 취급하지 않음 |
| 메뉴 단계 “아이스 카페라떼 추가 옵션 없이 포장” | `select_menu`, `COLD`/`TAKEOUT`, 커스터마이징 `resolved`, 빈 `option_ids`와 `intents` | 메뉴 확인 후 최종 주문 확인으로 이동 |
| 메뉴 확인 단계 “네, 샷도 추가해 주세요” | `confirm`, 현재 메뉴·온도에 유효하면 `shot:extra` | 기존 온도·이용 방식을 유지하고 샷 선택 추가 |
| 온도 단계 “핫이나 아이스” | `retry`, 온도 생략, `unresolved_fields: ["temperature"]` | 이전 온도로 자동 진행하지 않고 다시 선택 |
| 커스터마이징 단계 “샷 추가하고 시럽도” | `set_options`, `option_ids: ["shot:extra"]`, `needs_clarification`, `unresolved: ["시럽"]` | 샷은 선택된 상태로 표시하고 화면에서 시럽 확인 |
| HOT 전용 메뉴의 온도 단계 “아이스” | `retry/INVALID_OPTION`, 온도 생략, `unresolved_fields: ["temperature"]` | HOT으로 조용히 대체하지 않음 |

커스터마이징을 하나라도 명확히 지정하고 모든 요청을 해결했으면 추가 옵션 화면 전체를 생략하며 언급하지 않은 그룹은 추가 선택 없음으로 둔다. 미해결 표현은 화면에서 선택 후 계속하기 또는 “추가 옵션 없이”로 명시적으로 확인할 수 있다. 최종 주문 요청에는 `intents`, `unresolved`, 가격을 보내지 않고 검증된 `option_ids`만 전달한다. 서버가 현재 메뉴의 옵션 ID와 선택 개수를 다시 검증하고 추가 금액을 계산한다.

`temperature`/`service_type` 단계에서는 선택적 폼 필드 `selected_temperature=HOT|COLD`를 전달해 커스터마이징을 검증할 수 있다. `menu_confirmation`에서도 선택 메뉴와 온도를 전달할 수 있으며 `customization` 단계는 둘 다 필수다. 메뉴 맥락 없이 온도를 보내거나 메뉴가 제공하지 않는 온도를 보내면 `422 INVALID_VOICE_CONTEXT`다. 메뉴 직접 선택은 해당 메뉴와 발화 온도(또는 유일한 제공 온도)로 검증한다. 추천 경로는 메뉴 확정 전이므로 커스터마이징 의도를 보존하며, 추천이 발화 온도 또는 실제 제공 온도와 충돌하면 `502 LLM_RECOMMENDATION_FAILED`다.

현재 단계의 `action` 검증과 별도로 옵션을 반환한다. `retry` 응답의 옵션만으로 주문을 진행하면 안 되며 `unresolved_fields`는 기존 선택의 자동 확정을 막는다. 재추천 행동에는 이전 요청 옵션을 전달하지 않는다. 메뉴 확인 단계는 “네, 포장이요” 같은 복합 확인을 지원하지만 최종 주문 확정의 기존 명시적 확인 규칙은 유지한다.

프론트는 발화에서 새로 지정한 항목만 세션에 병합한다. 추천·터치 메뉴 선택·메뉴 확인·온도 선택을 거쳐 원래 커스터마이징 의도를 보존하고, 현재 메뉴/온도에서 검증된 값만 주문에 적용한다. 커스터마이징 음성 입력의 `set_options`는 `needs_clarification` 상태도 반환할 수 있으므로 그 경우 유효한 선택을 표시한 채 같은 화면에서 확인받는다. 재추천·홈 이동에서는 세션을 초기화하고, 터치 선택 이후 늦은 음성 응답은 적용하지 않는다.

7.1의 오디오 오류와 처리량 제한을 공유하며, 다음 오류를 추가한다.

| HTTP | code | 조건 |
| --- | --- | --- |
| 422 | FastAPI 기본 `detail` 배열 | 필수 폼 필드 누락, `stage` 값 오류 또는 메뉴 ID 형식 오류 |
| 422 | `INVALID_VOICE_CONTEXT` | 단계에 필요한 메뉴 ID 누락, 미등록 ID, 중복 후보 또는 단계와 맥락 불일치 |
| 502 | `TRANSCRIPTION_FAILED` | 전사 워커가 실패했거나 유효한 응답을 반환하지 않음 |
| 503 | `TRANSCRIPTION_UNAVAILABLE`, `TRANSCRIPTION_BUSY`, `CATALOG_UNAVAILABLE` | 워커 미설정·연결 불가, 워커의 동시 요청 한도 초과, 또는 DB 카탈로그 조회 실패 |
| 504 | `TRANSCRIPTION_TIMEOUT` | 전사 워커 응답 대기 시간이 75초 초과 |

Whisper는 공용 서버의 전사 워커에서 미리 로드한다. 워커는 기본으로 두 건을 받고, 첫 녹음 도착 후 150 ms 안에 두 번째 녹음이 준비되면 한 배치로 전사한다. FastAPI는 내부 `VOICE_TRANSCRIPTION_URL`로 변환된 PCM을 보내고 전사 텍스트를 받는다. 브라우저 전체 요청 제한은 전사와 LLM 요청을 포함해 140초다.

## LLM 직접 추천 결과

등록 메뉴명과 일치하지 않는 전사는 현재 DB 메뉴 45종과 함께 LLM에 전달한다. 서버는 결과의 메뉴 ID·온도·판매·가격·근거를 검증한다. 별도 텍스트 추천 API나 Pretuning 관리 API는 제공하지 않는다.

```json
{"transcript":"차가운 음료 추천", "action":{"type":"direct_recommendation","engine":"llm-direct","status":"recommend","recommendations":[{"menu_id":"iced_americano","temperature":"COLD","reason":"확인된 자료에 기반한 근거"}],"questions":[],"missing_information":[]}, "recognized_options":{"temperature":"COLD","unresolved_fields":[]}}
```

`status`는 `recommend`, `insufficient_data`다. 추천 개수를 말하면 그 개수를 상한으로 사용하고, 말하지 않으면 현재 메뉴 수까지 적합한 후보를 반환한다. 같은 메뉴 ID는 중복하지 않는다. `questions`는 항상 빈 배열이다. 자료 부족은 후보 없이 반환하고 화면에는 빈 추천 목록과 재추천 버튼을 표시한다. 추천 단계의 `candidate_menu_ids`도 전체 후보 수를 허용한다. 재추천은 `restart_recommendation`, 정확한 메뉴 선택은 `select_menu`, 단계별 옵션과 주문 확인은 기존 행동을 사용한다. LLM 실패는 502 `LLM_RECOMMENDATION_FAILED`, 근거 자료 미준비는 503 `LLM_EVIDENCE_NOT_READY`다. 성공처럼 보이는 기본 후보나 점수 추천으로 대체하지 않는다.

현재 자료 상태·모델 설정은 [LLM 직접 추천 안내](llm-direct.md)를 참고한다.
