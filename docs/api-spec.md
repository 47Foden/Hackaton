# API 명세 — 기본 주문 흐름

## 1. 기준과 구현 상태

우선순위는 **common 데이터 → 이 문서와 DB 명세의 구체화된 계약 → [기본 주문 계획](plan/basic-order-flow.md)의 제안 → 이전 기획**이다. 사용자가 언급한 docs/basic-order-flow.md의 실제 경로는 docs/plan/basic-order-flow.md다.

GET /api/health, GET /api/menus, POST /api/orders는 구현됐다. 음성·추천·Pretuning 관리 API는 후속 설계다.

- 메뉴명·순서·분류: [menu_data.py](../common/menu_data.py)의 MENUS/CATEGORIES.
- 가격: [menu_prices.json](../common/menu_prices.json). 메뉴 단위 정수 원화이며 온도별 가산금은 없다.
- 온도·이미지: [menu_images.json](../common/menu_images.json)의 HOT/COLD 키와 정적 자산 경로.
- 가격·이미지 근거: common/menu_price_sources.json, common/menu_image_sources.json. 가격은 전국 공통 공식 가격을 보장하지 않으며 에스프레소는 모바일쿠폰 가격이다.
- common은 카탈로그의 기준 원본, PostgreSQL은 이를 반영한 조회 데이터와 주문 기록의 원본이다. 요청마다 사이트를 수집하거나 가격을 추정하지 않는다.

## 2. 메뉴 ID와 데이터 매핑

common의 한글 메뉴명은 변경하지 않는다. 아래 ID는 API/DB 연결용 고정 매핑이며 배열 위치에서 매번 생성하지 않는다. 레몬티와 레몬차는 같은 공식 상품·이미지를 사용하지만 별개 메뉴로 유지한다.

| menu_id | name | price_krw | available_temperatures | categories |
| --- | --- | ---: | --- | --- |
| peach_iced_tea | 복숭아 아이스티 | 3000 | COLD | 티 |
| lemon_tea_alias | 레몬티 | 3300 | HOT, COLD | 티 |
| iced_americano | 아이스아메리카노 | 2000 | COLD | 커피 |
| lemonade | 레몬에이드 | 3500 | COLD | 에이드 |
| strawberry_latte | 딸기라떼 | 3700 | COLD | 논커피라떼, 라떼 |
| green_grape_ade | 청포도에이드 | 3500 | COLD | 에이드 |
| cafe_latte | 카페라떼 | 2900 | HOT, COLD | 커피, 라떼 |
| lemon_tea | 레몬차 | 3300 | HOT, COLD | 티 |
| citron_tea | 유자차 | 3300 | HOT, COLD | 티 |
| espresso | 에스프레소 | 1500 | HOT | 커피 |
| green_tea_latte | 녹차라떼 | 3500 | HOT, COLD | 논커피라떼, 라떼 |

기존 초안의 lemon_iced_tea, matcha_latte는 사용하지 않는다. 카테고리는 CATEGORIES의 순서로 반환하며 중복 소속을 허용한다. 녹차라떼는 이름에 녹차가 있어도 티 카테고리에 추가하지 않는다.

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

쿼리/본문 없음. 성공 200, display_order 오름차순, 동점은 menu_id COLLATE "C" 오름차순으로 정렬한 menus 배열. 아래 예시는 한 건이며 정상 seed는 11건이다. 판매 중지 메뉴도 is_available=false로 반환한다.

```json
{
  "menus": [
    {
      "menu_id": "peach_iced_tea",
      "name": "복숭아 아이스티",
      "categories": ["티"],
      "price_krw": 3000,
      "available_temperatures": ["COLD"],
      "variants": [
        {"temperature":"COLD","image_url":"/images/menus/peach-iced-tea-ice.jpg"}
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
| menu_id, name | 필수 비어 있지 않은 문자열, 위 고정 매핑 |
| categories | 필수 문자열 배열, CATEGORIES의 소속 목록 |
| price_krw | 필수 0 이상 정수, 현재 PRICE_OPTIONS의 값이며 메뉴별 common 가격과 일치 |
| available_temperatures | 필수 비어 있지 않은 배열. HOT, COLD 순서, 중복 없음 |
| variants | 각 제공 온도마다 정확히 한 객체. 온도 집합은 available_temperatures와 동일 |
| variants[].image_url | 필수 문자열, common의 해당 온도 경로 |
| image_url | 기본 카드 이미지. COLD가 있으면 COLD, 없으면 HOT 이미지 |
| is_available, is_featured | 필수 boolean |
| display_order | 필수 양의 정수 |

이미지는 프론트 origin의 frontend/public 아래에서 제공한다. 백엔드가 이미지 파일을 JSON으로 전송하지 않는다. 이미지 요청 실패 시 화면이 대체 이미지를 표시하되 메뉴 이름·가격은 유지한다. 계획의 nullable 이미지/온도별 가격 제안보다 현재 common을 우선하므로 응답 가격은 메뉴당 하나다.

온도가 한 가지면 프론트가 자동 선택해 이용 방식 단계로 이동한다. 두 가지면 선택 화면을 표시한다. 자동 선택한 온도도 최종 확인과 주문 요청에 반드시 담는다.

메뉴가 없으면 200과 `{"menus":[]}`를 반환한다. DB 조회 실패/테이블 미적용과 카탈로그 응답 무결성 오류는 503 CATALOG_UNAVAILABLE이다. seed 검증은 빈 온도나 누락 이미지를 가진 메뉴의 게시를 막아야 한다.

## 6. POST /api/orders — 구현됨

프론트는 최종 확인 화면의 주문 확정 버튼을 눌렀을 때 요청한다. `request_id`는 하이픈을 포함한 UUID 문자열이다. 아래 네 필드가 필수다.

```json
{"request_id":"550e8400-e29b-41d4-a716-446655440000","menu_id":"peach_iced_tea","temperature":"COLD","service_type":"TAKEOUT"}
```

새 요청은 한 트랜잭션에서 메뉴 존재, 판매 여부, 제공 온도를 검증하고 DB 가격으로 주문을 저장한다. 수량은 1이며 커밋 확인 후 `201`을 반환한다. 같은 UUID와 같은 주문 내용은 `200`과 기존 저장 결과를 반환한다.

```json
{
  "order_id":"1",
  "order_number":"1",
  "menu_id":"peach_iced_tea",
  "menu_name":"복숭아 아이스티",
  "temperature":"COLD",
  "service_type":"TAKEOUT",
  "quantity":1,
  "total_price_krw":3000,
  "created_at":"2026-11-07T00:00:00Z"
}
```

order_id와 order_number는 같은 orders.id를 문자열로 표현한다. 일일 초기화·고정 자릿수·무결번을 보장하지 않는다. menu_name과 금액은 주문 시점 스냅샷이다. 주문 저장은 결제 성공을 뜻하지 않는다.

### 오류 계약

업무 오류 형태: `{"detail":{"code":"INVALID_OPTION","message":"선택할 수 없는 온도입니다."}}`.

| HTTP | code | 조건 |
| --- | --- | --- |
| 404 | MENU_NOT_FOUND | 등록되지 않은 menu_id |
| 409 | MENU_UNAVAILABLE | 판매 중지 |
| 409 | IDEMPOTENCY_CONFLICT | 이미 저장된 UUID에 다른 메뉴, 온도 또는 이용 방식이 들어옴 |
| 422 | INVALID_OPTION | enum 자체는 유효하지만 그 메뉴가 제공하지 않는 온도 |
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

multipart 요청 전체는 오디오 제한에 헤더 여유 16 KiB를 더해 파싱 전에 제한한다. 프로세스당 음성 요청 한 건을 업로드부터 변환 완료까지 처리한다. 업로드 수신은 5초, ffprobe와 FFmpeg에는 합쳐서 5초, 브라우저 요청에는 15초를 적용한다. 초과 시 화면은 **다시 녹음**을 제공한다.

| HTTP | code | 조건 |
| --- | --- | --- |
| 408 | `AUDIO_UPLOAD_TIMEOUT` | 업로드 수신 타임아웃 |
| 413 | `AUDIO_TOO_LARGE`, `AUDIO_TOO_LONG` | 파일 크기 또는 변환된 길이 초과 |
| 415 | `UNSUPPORTED_AUDIO`, `AUDIO_FORMAT_MISMATCH` | 확장자·MIME 오류 또는 실제 컨테이너·코덱 불일치 |
| 422 | `EMPTY_AUDIO`, `INVALID_AUDIO` | 빈 파일 또는 디코딩 실패 |
| 503 | `AUDIO_BUSY`, `AUDIO_TOOLS_UNAVAILABLE` | 다른 요청 처리 중이거나 FFmpeg 또는 ffprobe가 설치되지 않음 |
| 504 | `AUDIO_TIMEOUT` | 검사 또는 변환 도구 타임아웃 |

### 7.2 `POST /api/voice/interpret` — 전사와 주문 단계 해석 제안

음성 전사와 해석 연결은 후속이다. multipart `audio`와 `stage`, 필요한 경우 `selected_menu_id`와 `candidate_menu_ids`를 받아 `transcript` 및 `select_menu`, `set_temperature`, `set_service_type`, `recommend`, `retry` 행동을 반환하는 계약을 제안한다. 최종 주문 확정은 화면의 주문 확정 버튼에서 수행한다.

공용 서버에서는 Whisper를 미리 로드하고, 전사 초기 예산 25초와 전체 클라이언트 요청 예산 40초를 사용한다. 공용 서버 실측 후 조정한다.

기존 Pretuning·추천 설계는 아래에 보존한다. 데이터와 충돌할 경우 위 common 매핑이 우선하며, 관리 작업의 request_id 정책을 기본 주문 API에 적용하지 않는다.

---

# 부록 — 후속 Pretuning·추천 설계

## 1. 목적과 구현 상태

11개 메뉴를 행으로, 메뉴 종류·맛·가격을 열로 갖는 두 데이터프레임을 사전에 생성합니다. 종류는 이진 값으로 지정하고, 검색 근거에 기반한 맛 평가는 OpenAI 모델을 5회 호출한 뒤 평균을 냅니다.

여기서 **Pretuning은 프로젝트 내부 명칭**입니다. 이번 작업은 모델 가중치를 학습하거나 파인튜닝하는 것이 아니라, 기존 모델로 추천용 메뉴 속성표를 생성하는 작업입니다. 단맛·신맛·쓴맛은 서로 배타적인 다중분류 확률이 아닌 **각각 독립적인 연속 점수**이며, 합이 1일 필요가 없습니다.

현재 실제 구현된 API는 `GET /api/health`, `GET /api/menus`, `POST /api/orders`입니다. 아래 생성·조회·추천 API와 필드명은 이번 요구사항을 반영한 설계 초안이며 아직 구현하지 않았습니다. 실제 5회 평가 결과도 아직 생성하지 않았습니다.

## 2. 공통 규칙

- 개발 서버: `http://localhost:8000`. 프론트에서는 `/api/...`로 호출합니다.
- 요청과 응답: `application/json`, UTF-8.
- 메뉴 ID는 아래 표의 문자열을 사용하며 두 데이터프레임에서 같은 ID·행 순서를 유지합니다.
- API 키는 백엔드 환경변수 `OPENAI_API_KEY`로 읽습니다. 요청·응답·결과 파일에 키를 넣지 않습니다.
- 요청 모델 표기 `gpt-6luna`는 공식 목록 표기인 `gpt-6-luna`로 정리합니다. 실제 계정의 호출 권한은 실행 전에 확인하며 다른 모델로 자동 대체하지 않습니다. [OpenAI 모델 가격 목록](https://platform.openai.com/pricing)
- 이 문서의 맛 숫자 예시는 응답 형식을 설명하기 위한 값이며 검색·모델 실행 결과가 아닙니다.

## 3. 메뉴와 이진 속성

`binary_df`의 인덱스는 `menu_id`, 데이터 열은 `coffee`, `tea`, `ade`, `latte`, `non_coffee_latte`입니다. 값은 정수 `0` 또는 `1`입니다. 메뉴명은 별도 메뉴 목록에서 ID로 연결합니다.

사용자가 확정한 종류 구분을 적용합니다. **라떼 열은 카페라떼·딸기라떼·녹차라떼 모두 1**, **논커피라떼 열은 딸기라떼·녹차라떼만 1**입니다. 카페라떼는 커피 열도 1이므로 전체 종류 열이 서로 배타적인 것은 아닙니다. 녹차라떼의 티 열은 0으로 둡니다. 평가 브랜드는 **메가MGC커피(메가커피)**로 확정합니다.

| menu_id | 메뉴 | 커피 | 티 | 에이드 | 라떼 | 논커피라떼 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| peach_iced_tea | 복숭아 아이스티 | 0 | 1 | 0 | 0 | 0 |
| lemon_tea_alias | 레몬티 | 0 | 1 | 0 | 0 | 0 |
| iced_americano | 아이스아메리카노 | 1 | 0 | 0 | 0 | 0 |
| lemonade | 레몬에이드 | 0 | 0 | 1 | 0 | 0 |
| strawberry_latte | 딸기라떼 | 0 | 0 | 0 | 1 | 1 |
| green_grape_ade | 청포도에이드 | 0 | 0 | 1 | 0 | 0 |
| cafe_latte | 카페라떼 | 1 | 0 | 0 | 1 | 0 |
| lemon_tea | 레몬차 | 0 | 1 | 0 | 0 | 0 |
| citron_tea | 유자차 | 0 | 1 | 0 | 0 | 0 |
| espresso | 에스프레소 | 1 | 0 | 0 | 0 | 0 |
| green_tea_latte | 녹차라떼 | 0 | 0 | 0 | 1 | 1 |

종류 값은 모델에 5회 질문하거나 평균 내지 않습니다. 논커피라떼는 커피가 없는 라떼를 뜻하며, 무카페인을 보장하는 속성으로 사용하지 않습니다.

## 4. 연속 속성과 정규화

`continuous_df`의 인덱스는 같은 `menu_id`, 데이터 열은 `sweetness`, `sourness`, `bitterness`, `price_normalized`입니다. 각 값은 0~1입니다.

| 열 | 의미 | 생성 방법 |
| --- | --- | --- |
| sweetness | 단맛 강도 | 모델 5회 평가의 정규화 평균 |
| sourness | 신맛 강도 | 모델 5회 평가의 정규화 평균 |
| bitterness | 쓴맛 강도 | 모델 5회 평가의 정규화 평균 |
| price_normalized | 상대적인 가격 수준, 높을수록 비쌈 | 실제 가격으로 수식 계산 |

### 맛 평가 기준

- 각 호출에서 메뉴별 세 맛을 각각 0~10으로 평가하고, 원시 점수를 보관합니다.
- 공통 기준: 0은 감지되지 않음, 2.5는 약함, 5는 중간, 7.5는 강함, 10은 매우 강함입니다. 모든 메뉴·회차에 같은 기준을 사용합니다.
- 메가커피의 해당 메뉴 기본 레시피·기본 크기를 기준으로 하며 추가 시럽 등 사용자 변경은 제외합니다. 기본 레시피에 포함된 시럽은 유지합니다. 온도 등 조건이 불명확하면 기록하고 서로 다른 변형을 섞지 않습니다.
- 정규화: `normalized_score = raw_score / 10`.
- 최종 점수: `mean = (raw_1 + raw_2 + raw_3 + raw_4 + raw_5) / 50`.
- 집계 전 반올림하지 않으며 최종 표시에서 소수점 4자리까지 사용합니다.
- 각 속성별 5회 원시 점수, 정규화 평균, 최솟값·최댓값, 모집단 표준편차도 감사용 결과에 보관합니다. 표준편차는 정규화한 5개 값에 대해 분모 5로 계산합니다.
- 모델 평가값은 검색 자료로 추정한 맛 강도이며 실측 관능평가가 아닙니다. 동일 모델의 5회 평균이 정확성이나 독립적인 5명 평가를 보장하지는 않습니다.

### 가격

허용 가격 집합은 common/menu_data.py의 PRICE_OPTIONS를 따른다. 현재 `[1500, 2000, 2900, 3000, 3300, 3500, 3700]`이다. 메뉴별 가격은 이미 common/menu_prices.json에 있으며 모델로 추정하거나 목록 순서대로 재배정하지 않는다.

```text
price_normalized = (price_krw - 1500) / (3700 - 1500)
```

정규화 경계는 데이터셋 생성 시 PRICE_OPTIONS의 min/max로 구하고 버전과 함께 저장한다. common 가격이 바뀌면 새 데이터셋을 생성하며 게시된 결과를 조용히 변경하지 않는다. min=max이면 나눗셈하지 않고 데이터셋 생성을 거부한다. 레몬티와 레몬차는 별개 행으로 유지한다. 공통 데이터의 라떼 분류와 한글 속성을 API 영문 열로 매핑한다: 커피→coffee, 티→tea, 에이드→ade, 라떼→latte, 논커피라떼→non_coffee_latte, 단맛→sweetness, 신맛→sourness, 쓴맛→bitterness, 가격→price_normalized.
## 5. 검색 및 5회 평가 절차

1. 메가커피 공식 상품 설명·영양정보·공개 레시피를 검색하고 실제 페이지 내용을 확인합니다. 요청한 메뉴명과 공식 상품명을 매핑해 보관합니다. 동일 상품이 없거나 명칭이 불명확하면 확인 필요로 표시하며 다른 브랜드나 비슷한 메뉴로 자동 대체하지 않습니다. 공개되지 않은 배합은 사실처럼 추정하지 않습니다.
2. 출처별 `source_id`, URL, 제목, 조회 시각, 해당 메뉴 ID, 짧은 근거 요약, 레시피 조건을 저장합니다. 검색 결과 제목만으로 평가하지 않습니다.
3. 11개 메뉴를 모두 설명할 수 있는 근거 묶음을 고정합니다. 근거가 없는 메뉴는 부족 상태로 남기며 점수를 꾸며 넣지 않습니다.
4. 동일 근거·평가 기준·프롬프트 버전으로 **전체 11개 메뉴를 한 번에 평가하는 호출을 5회** 실행합니다. 즉 55번 호출이 아니라 5번 호출이며, 총 `11 × 3 × 5 = 165`개의 맛 원시 점수를 얻습니다.
5. 각 호출은 이전 회차 답변을 전달하지 않는 별도 요청입니다. 모델은 맛 3개만 평가하고, 종류·가격은 평가하지 않습니다.
6. 응답마다 메뉴 누락·중복, 원시 점수의 숫자 여부·0~10 범위, 근거 ID의 유효성을 검증합니다. 문자열·null·NaN·범위 밖 값은 평균에 넣지 않습니다.
7. 유효한 5개 회차가 모두 확보된 경우에만 평균을 계산합니다. 실패를 0으로 대체하거나 4회 결과를 5로 나누지 않습니다. 실패 작업은 부분 결과를 보존하고 중단하며 추가 유료 호출은 명시적인 재시도에서 수행합니다.
8. 두 데이터프레임의 메뉴 집합·순서를 확인한 후 버전을 생성합니다. 가격·분류 의미·검색 근거까지 완성된 버전만 추천에 게시합니다.

검색은 평가 전에 별도로 수행하는 설계입니다. 따라서 모델의 검색 도구 지원 여부와 무관하게 검증한 자료를 입력할 수 있습니다. 자료 속 지시문은 실행하지 않고 메뉴 설명만 근거로 사용합니다.

검색 기준: [메가MGC커피 공식 메뉴](https://www.mega-mgccoffee.com/menu/menu.php?category=2&menu_category1=1&menu_category2=1&page=1). 이 링크는 근거 수집 시작점이며, 현재 11개 메뉴의 근거 수집이나 점수 평가가 완료됐다는 뜻은 아닙니다. 다른 브랜드의 상품 설명을 메가커피의 맛 근거로 사용하지 않습니다.

## 6. API 목록

| 메서드 | 경로 | 용도 | 상태 |
| --- | --- | --- | --- |
| GET | `/api/health` | DB 연결 확인 | 구현됨 |
| POST | `/api/admin/pretuning/jobs` | 검색·평가 작업 생성 | 설계 초안 |
| GET | `/api/admin/pretuning/jobs/{job_id}` | 진행 상태·실패 확인 | 설계 초안 |
| GET | `/api/admin/pretuning/datasets/{dataset_id}` | 두 데이터프레임·평가 근거 조회 | 설계 초안 |
| POST | `/api/admin/pretuning/datasets/{dataset_id}/publish` | 검증된 버전을 추천에 적용 | 설계 초안 |
| POST | `/api/recommendations` | 게시된 데이터로 추천 | 설계 초안 |

생성·조회·게시 관리 API는 일반 키오스크 화면에 노출하지 않습니다. 구현 시 관리자 인증을 필수로 적용하며, 인증 없는 유료 생성 엔드포인트로 배포하지 않습니다. 구체적인 인증 방식은 미정입니다.

### 6.1 `GET /api/health`

요청 본문 없음. 성공은 `200`과 `{"status":"ok","database":"connected"}`입니다. 현재 코드가 처리하는 `psycopg.Error`는 `503`과 `{"detail":"Database unavailable"}`를 반환합니다. OpenAI·검색·속성표 준비 상태는 검사하지 않습니다.

### 6.2 `POST /api/admin/pretuning/jobs`

요청 예시:

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "model": "gpt-6-luna",
  "runs": 5,
  "catalog_version": "menu-v1",
  "recipe_profile": "메가MGC커피 기본 레시피·기본 크기, 기본 시럽 유지, 추가 시럽 없음",
  "source_policy": "official_first"
}
```

모든 필드는 필수입니다. `request_id`는 UUID, `runs`는 5로 고정, `model`과 `source_policy`는 위 값만 허용합니다. `catalog_version`은 11개 메뉴와 가격·이진 속성을 담은 사전 등록 버전이며, 등록 방법은 별도 관리 기능에서 정의합니다. `recipe_profile`은 비어 있지 않은 문자열이어야 합니다.

응답 `202 Accepted`:

```json
{"job_id":"pt-job-001","status":"queued"}
```

같은 요청 ID·같은 내용의 재전송은 `200`으로 기존 작업 ID와 현재 상태를 반환하고 추가 호출을 만들지 않습니다. 같은 요청 ID·다른 내용은 `409`입니다. 동시 요청은 DB 유일 제약으로 막습니다. 관리자 요청 제한과 중복 방지 검증을 통과한 뒤 유료 평가를 시작합니다.

### 6.3 `GET /api/admin/pretuning/jobs/{job_id}`

응답 `200`:

```json
{
  "job_id": "pt-job-001",
  "status": "scoring",
  "completed_runs": 2,
  "required_runs": 5,
  "dataset_id": null,
  "error": null
}
```

상태는 `queued → researching → scoring → aggregating → completed`입니다. 근거·평가 실패는 `failed`, 가격 등 기준 데이터 미완성은 `needs_input`입니다. `completed`는 최종 데이터셋 생성 성공을 뜻하며 자동 게시하지 않습니다. 실패 시 `error`에는 비밀정보 없는 `code`, `message`를 담습니다. 완료 전 `dataset_id`는 null입니다.

### 6.4 `GET /api/admin/pretuning/datasets/{dataset_id}`

응답은 pandas 객체 대신 JSON의 열·행 구조로 반환합니다. **아래는 한 행만 보여주는 형식 예시이며 실제 응답에는 11행이 모두 필요합니다.**

```json
{
  "dataset_id": "pt-v1",
  "status": "draft",
  "model": "gpt-6-luna",
  "runs": 5,
  "binary_df": {
    "index_name": "menu_id",
    "columns": ["coffee", "tea", "ade", "latte", "non_coffee_latte"],
    "rows": [{"menu_id":"peach_iced_tea","values":[0,1,0,0,0]}]
  },
  "continuous_df": {
    "index_name": "menu_id",
    "columns": ["sweetness", "sourness", "bitterness", "price_normalized"],
    "rows": [{"menu_id":"peach_iced_tea","values":[0.7,0.2,0.1,0.6818]}]
  },
  "audit_url": "/api/admin/pretuning/datasets/pt-v1?include_audit=true"
}
```

`include_audit`는 생략 시 false인 불리언 값입니다. true이면 추가 `audit` 필드에 회차별 응답 ID·모델명·시각·원시 평가 결과, 프롬프트 버전, 출처와 요약, 가정, 속성별 평균·표준편차·최솟값·최댓값을 포함합니다. 키나 인증 헤더는 저장하지 않습니다.

최종 결과는 `binary_df.csv`(11×5), `continuous_df.csv`(11×4)로도 출력하는 설계입니다. 크기에 인덱스는 포함하지 않습니다. `menu_catalog.json`, `evaluation_audit.json`은 보조 파일로 보관합니다. 이는 추천 데이터 출력이며 주문 기록을 CSV에 저장한다는 의미가 아닙니다.

### 6.5 `POST /api/admin/pretuning/datasets/{dataset_id}/publish`

요청 본문은 없습니다. 11개 메뉴·각 5회 유효 평가·확정 가격·점수 범위·출처·분류 정의를 검증한 뒤 활성 버전을 한 번에 전환합니다. 실패하면 기존 버전을 유지합니다.

성공 `200`: `{"dataset_id":"pt-v1","status":"published"}`. 같은 버전의 재요청은 같은 결과를 반환합니다. 공개된 버전은 수정하지 않고 새 결과는 별도 버전으로 만듭니다.

### 6.6 `POST /api/recommendations`

해석된 조건을 받아 사전 계산된 속성표로 추천합니다. 자연어를 조건으로 변환하는 API는 별도로 정의합니다. 이 단계에서 모델을 매번 다시 호출하지 않습니다.

```json
{
  "filters": {"tea": 1},
  "targets": {"sweetness": 0.8, "sourness": 0.2},
  "weights": {"sweetness": 1.0, "sourness": 1.0},
  "max_price_krw": 5000,
  "limit": 4
}
```

- `filters`: 생략 시 `{}`. 이진 열 이름과 0 또는 1만 허용하며 조건은 AND로 적용합니다.
- `targets`: 필수. 연속 열 이름 1개 이상과 0~1의 목표 점수를 전달합니다.
- `weights`: 생략 시 지정된 목표 속성에 같은 가중치를 적용합니다. 지정하면 targets와 동일한 키 집합, 0 이상의 유한한 수, 양수인 가중치 합이 필요합니다.
- `max_price_krw`: 선택, 0 이상의 정수. 생략하면 가격 상한이 없습니다. 실제 판매 가격으로 필터링합니다.
- `limit`: 1~4의 정수, 기본값 4.

초기 순위 계산은 다음 공식을 제안하며 추천 품질을 검증한 뒤 확정합니다.

```text
score = 1 - sum(weight[j] * abs(menu[j] - target[j])) / sum(weight[j])
```

종류·가격 상한·판매 가능 여부로 먼저 거르고, 지정된 속성만 계산해 높은 점수부터 최대 4개를 반환합니다. 동점은 menu_id 오름차순입니다. ‘달지 않은’은 단맛 목표를 낮게 설정하며 전체 속성 순위를 뒤집지 않습니다. 지정하지 않은 속성을 0으로 간주하지 않습니다.

성공 `200` (형식 예시):

```json
{"dataset_id":"pt-v1","recommendations":[{"menu_id":"peach_iced_tea","score":0.95}]}
```

후보가 없으면 `recommendations: []`, 공개된 데이터가 없으면 `503 DATASET_NOT_READY`입니다. 응답에 버전을 표시하고 한 요청에서 다른 버전의 데이터를 섞지 않습니다.

## 7. 오류 응답 — 신규 API

```json
{"detail":{"code":"MISSING_PRICE","message":"메뉴별 가격을 설정해 주세요."}}
```

| HTTP | code | 조건 |
| --- | --- | --- |
| 401 / 403 | `UNAUTHORIZED` / `FORBIDDEN` | 관리 API 인증·권한 부족 |
| 404 | `NOT_FOUND` | 작업·데이터셋·카탈로그 버전 없음 |
| 409 | `IDEMPOTENCY_CONFLICT` | 동일 요청 ID의 내용 불일치 |
| 409 | `DATASET_INCOMPLETE` | 미완성 데이터 게시 시도 |
| 422 | `MISSING_PRICE` / `INVALID_PRICE` | 가격 누락·허용 집합 밖의 가격 |
| 422 | `INVALID_CATALOG` | 메뉴 누락·중복·이진 값 오류 |
| 429 | `RATE_LIMITED` | 관리 API 요청 상한 초과 |
| 503 | `OPENAI_NOT_CONFIGURED` | 서버 키 미설정 |
| 503 | `MODEL_UNAVAILABLE` | 지정 모델 사용 불가 |
| 503 | `DATASET_NOT_READY` | 추천용 공개 버전 없음 |

비동기 접수 후 실패는 작업 조회 응답의 `error`에 표시합니다. 예: `INSUFFICIENT_SOURCES`, `MODEL_RESPONSE_INVALID`, `UPSTREAM_RATE_LIMITED`, `UPSTREAM_TIMEOUT`. 자료형·필수 필드 검증은 FastAPI 기본 422 응답(detail 배열)을 사용하고 위 업무 오류와 구분합니다.

## 8. 현재 미완료 사항

- 사용자가 키 설정을 건너뛰었으므로 실제 모델 호출과 5회 평가는 보류합니다. 추후 기존 키를 사용할 수 있게 되면 접근을 검증합니다.
- 메뉴명·분류·가격·온도·이미지는 common을 사용합니다. 맛 평가 근거 수집과 실제 평가만 후속 작업입니다.
- 메뉴별 검색 근거 수집, 관리 API·평가·출력·추천 처리는 구현 예정입니다.
- 유효한 5회 평가가 끝난 뒤 최종 데이터프레임을 생성합니다. 문서의 예시 점수를 실제 결과로 사용하지 않습니다.

## 메뉴 조회 구현 위치 및 검증

- backend/app/routers/menus.py: GET /api/menus 라우터, 503 오류 변환.
- backend/app/schemas/menus.py: 엄격한 응답 자료형과 온도/이미지 일치 검증.
- backend/app/repositories/menus.py: 일관된 DB 스냅샷, 고정 정렬, 이미지/카테고리 조립.
- backend/tests/test_menus_api.py: 실제 ASGI 앱과 별도 PostgreSQL 스키마를 사용하는 응답·판매 상태·동점 정렬·빈 목록·503 검사.

판매 중지나 is_featured 플래그는 응답 포함 여부와 전체 메뉴 정렬을 바꾸지 않는다. 프론트가 is_available로 선택 가능 여부를 결정하고, is_featured로 간편 목록을 구성한다. 대표 이미지는 COLD 우선이고 온도별 이미지는 variants에 모두 반환한다. GET은 읽기만 하며 seed나 파일 수집을 실행하지 않는다.

현재 실행 중인 백엔드 HTTP 200과 메뉴 11개·온도 16개·간편 표시 4개 및 OpenAPI 등록을 확인했다. DB/메뉴 API 통합 테스트 10개를 통과했다. 프론트의 HTTP 어댑터 전환과 주문 API 구현은 후속이다.
