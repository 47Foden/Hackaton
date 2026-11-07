# DB 명세 — 메뉴와 기본 주문

## 1. 기준과 범위

테이블 migration, 사전 검증을 포함한 seed, DB 연결, 메뉴 조회 및 주문 저장 API를 구현했다. PostgreSQL 17과 현재 psycopg를 사용하고 ORM 추가를 필수로 하지 않는다.

우선순위: **common → [API 명세](api-spec.md)와 이 DB 명세 → [기본 주문 계획](plan/basic-order-flow.md)**. common 자체는 변경하지 않는다. API 명세 2절의 고정 ID 매핑을 사용한다.

- common/menu_data.py: 11개 메뉴, 순서, 중복 가능한 카테고리, 허용 가격.
- common/menu_prices.json: 메뉴별 단일 가격 원본.
- common/menu_images.json: 메뉴별 제공 온도와 온도별 이미지 경로.
- common/menu_price_sources.json, menu_image_sources.json: 가격/이미지의 출처와 확인일. seed와 함께 참조한다.
- 카탈로그는 common에서 명시적으로 DB에 반영한다. 주문 기록은 PostgreSQL이 유일한 원본이다.
- 메뉴 1개·수량 1개, 최종 확인 후 저장. 결제·다품목·CSV 저장·일일 번호 초기화·중복 요청 방지는 이번 범위에 없다.

## 2. 관계와 저장 책임

```text
menus ──< menu_categories
  │
  ├────< menu_variants
  │
  └────< orders (메뉴명·가격은 주문 시점 스냅샷)
```

| 테이블 | 역할 |
| --- | --- |
| menus | 고정 ID, 사용자 메뉴명, 공통 가격, 노출/판매 설정 |
| menu_categories | CATEGORIES의 다대다 소속. 카테고리별로 상품 행을 복제하지 않음 |
| menu_variants | 제공 온도와 이미지. common에 없는 온도별 가격은 만들지 않음 |
| orders | 메뉴 1개 주문, 선택 온도/이용 방식, 금액 스냅샷, 자동 증가 번호 |
| schema_migrations | 적용한 SQL 버전 및 체크섬 기록 |

레몬티와 레몬차는 각각 lemon_tea_alias와 lemon_tea 행을 가진다. 공식명이 같아도 합치지 않으며 이미지 경로 중복을 허용한다. 11개 메뉴에 온도 행은 16개이고, 두 레몬 메뉴가 이미지를 공유해 고유 이미지 파일은 14개다.

## 3. 목표 DDL

아래 DDL은 구현된 목표 스키마다. schema_migrations는 실행기가 생성하며 나머지는 backend/app/db/migrations/0001_menu_orders.sql로 적용한다. 웹 앱 시작 시 자동 적용하지 않는다.

```sql
CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE menus (
    menu_id TEXT PRIMARY KEY CHECK (btrim(menu_id) <> ''),
    name TEXT NOT NULL UNIQUE CHECK (btrim(name) <> ''),
    price_krw INTEGER NOT NULL CHECK (price_krw >= 0),
    is_available BOOLEAN NOT NULL DEFAULT TRUE,
    display_order INTEGER NOT NULL CHECK (display_order > 0),
    is_featured BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE menu_categories (
    menu_id TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE RESTRICT,
    category TEXT NOT NULL CHECK (
        category IN ('커피', '티', '에이드', '논커피라떼', '라떼')
    ),
    PRIMARY KEY (menu_id, category)
);

CREATE TABLE menu_variants (
    menu_id TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE RESTRICT,
    temperature TEXT NOT NULL CHECK (temperature IN ('HOT', 'COLD')),
    image_url TEXT NOT NULL CHECK (image_url LIKE '/images/menus/%'),
    PRIMARY KEY (menu_id, temperature)
);

CREATE TABLE orders (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    menu_id TEXT NOT NULL REFERENCES menus(menu_id) ON DELETE RESTRICT,
    menu_name_snapshot TEXT NOT NULL CHECK (btrim(menu_name_snapshot) <> ''),
    unit_price_krw INTEGER NOT NULL CHECK (unit_price_krw >= 0),
    temperature TEXT NOT NULL CHECK (temperature IN ('HOT', 'COLD')),
    service_type TEXT NOT NULL CHECK (service_type IN ('DINE_IN', 'TAKEOUT')),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity = 1),
    total_price_krw INTEGER NOT NULL CHECK (
        total_price_krw >= 0 AND total_price_krw = unit_price_krw * quantity
    ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

orders에는 menu_variants를 참조하는 복합 FK를 두지 않는다. 주문 시 제공 온도를 트랜잭션 안에서 검증하며, 이후 온도 제공이 중단되어도 과거 주문은 유지한다. CHECK만으로 현재 판매 상태·가격·제공 온도는 보장할 수 없으므로 주문 서비스를 통해 저장한다.

PRICE_OPTIONS와 정확한 common 가격 일치는 seed에서 검증한다. DB에는 변경 가능한 가격 집합을 하드코딩하지 않고 비음수 제약을 둔다. 이미지 파일 존재, 11개 메뉴의 완전성, 메뉴마다 최소 한 온도가 있는지도 seed에서 검증한다. 판매 종료는 is_available=false로 처리하고 과거 주문은 삭제하지 않는다.

## 4. seed와 common의 대응

| DB 항목 | 원본 / 처리 |
| --- | --- |
| menus.menu_id | API 명세의 고정 ID 매핑 |
| menus.name | MENUS의 문자열 그대로 |
| menus.price_krw | menu_prices.json[name] |
| menus.display_order | MENUS 위치 + 1 |
| menus.is_available | 새 행은 true, 기존 운영 값은 유지 |
| menus.is_featured | 새 행은 common/menu_display.json의 간편 목록 포함 여부. 기존 운영 설정 유지 |
| menu_categories | CATEGORIES에서 해당 메뉴가 속한 모든 카테고리 |
| menu_variants.temperature | menu_images.json[name]의 HOT/COLD 키 |
| menu_variants.image_url | 해당 키의 이미지 경로 |

API의 categories는 CATEGORIES 순서로, 온도는 HOT/COLD 순서로 정렬한다. 대표 이미지는 COLD가 있으면 COLD, 없으면 HOT에서 도출하고 DB에 중복 저장하지 않는다.

### 사전 검증

1. MENUS는 중복 없이 11개이며 ID 매핑·가격·이미지·가격 출처의 메뉴명 집합이 일치해야 한다.
2. 가격은 boolean을 제외한 비음수 정수이고 PRICE_OPTIONS에 포함되며 가격 출처의 값과 일치해야 한다.
3. 카테고리의 모든 메뉴는 MENUS에 존재해야 한다. 라떼 3종 중 딸기라떼·녹차라떼는 논커피라떼에도 소속된다.
4. 온도는 HOT/COLD만 허용하며 메뉴마다 최소 1개이고 이미지 출처의 온도와 일치해야 한다.
5. 모든 이미지 경로는 frontend/public/images/menus 안의 실제 파일이어야 한다. 레몬티와 레몬차의 이미지 공유는 허용한다.
6. 출처 URL·확인일은 common의 출처 파일에 보존한다. 가격을 전국 공통 공식 가격으로 설명하지 않는다.

검증 실패 시 기존 DB를 변경하지 않는다. 누락 가격을 0으로 채우거나 이미지 경로를 만들어 넣지 않는다.

### 적용과 재실행

검증 후 하나의 트랜잭션으로 카탈로그를 갱신한다. 동일 seed의 병렬 실행은 전용 advisory lock으로 직렬화한다. 기존 menus를 menu_id 순서로 잠그고 이름·가격·표시 순서를 UPSERT한다. 대상 메뉴의 카테고리와 온도는 common의 현재 값에 맞춘다. 모든 자식 테이블 변경은 부모 menus의 FOR UPDATE 잠금을 먼저 얻어야 한다.

동일 seed 재실행으로 행이 증가하지 않도록 PK를 사용한다. is_available/is_featured와 기존 주문은 보존한다. common에서 메뉴가 제거되면 자동 삭제하지 않고 사전 검증에서 중단해 별도 이관을 요구한다. 앱 시작마다 seed를 실행하지 않는다.

## 5. 주문 트랜잭션

READ COMMITTED에서 같은 연결·트랜잭션으로 처리하며 SQL은 바인드 파라미터를 사용한다.

1. UUID 요청 ID와 필수 선택값을 검증한다. 가격·수량 등 추가 요청 필드는 422로 거부한다.
2. UUID 기준의 트랜잭션 advisory lock을 얻은 뒤 별도 SELECT로 주문을 조회한다. 같은 UUID로 앞선 요청이 끝날 때까지 대기했다면 SELECT는 커밋된 최신 행을 읽는다.
3. 이미 저장된 주문의 메뉴·온도·이용 방식이 일치하면 기존 스냅샷을 `200`으로 반환한다. 내용이 다르면 `409 IDEMPOTENCY_CONFLICT`다.
4. 새 주문은 `menus` 행을 `FOR SHARE`로 잠그고 메뉴 존재, 판매 여부, 제공 온도를 검증한다.
5. UUID와 메뉴 이름·가격을 저장한다. 수량은 1, 합계는 DB 단가와 같다. 커밋 확인 후에만 `201`을 반환한다.

`0002_order_request_id`는 `orders.request_id UUID NOT NULL UNIQUE`를 추가한다. 기존 행에는 UUID를 채우고 주문번호와 스냅샷을 보존한다.

seed와 향후 관리 기능은 자식 테이블 수정 전에 부모 menus를 FOR UPDATE로 잠근다. 이 규칙을 통해 주문 중 가격·판매 여부·온도 변경과 충돌하지 않게 한다. 직접 SQL로 잠금 규약을 우회하지 않는다.

orders.id가 주문번호를 겸하며 문자열로 order_id/order_number에 반환된다. 번호 초기화·별도 카운터·무결번은 지원하지 않는다. 롤백에 따른 번호 누락을 허용하고 시퀀스를 되돌리지 않는다.

검증 오류 시 INSERT하지 않는다. DB 오류는 가능한 경우 ROLLBACK하고 503으로 변환한다. COMMIT 중 연결이 끊겼다면 같은 UUID와 주문 내용으로 수동 재시도해 저장 결과를 확인할 수 있다.

## 6. 주문 스냅샷과 API 대응

| API 응답 | DB 값 |
| --- | --- |
| order_id / order_number | str(orders.id) |
| menu_id | orders.menu_id |
| menu_name | orders.menu_name_snapshot |
| temperature / service_type / quantity | orders의 같은 이름 열 |
| total_price_krw | orders.total_price_krw |
| created_at | orders.created_at을 UTC ISO 8601로 변환 |

현재 필수 선택 속성은 온도와 이용 방식이다. 주문에 맛 평가·카테고리·녹음을 복사하지 않는다. 가격·메뉴명이 바뀌어도 과거 주문은 저장 당시 스냅샷으로 표시한다.

## 7. migration과 실행 환경

- 순서가 있는 SQL과 실행 스크립트는 backend/app/db에 구현되어 있다. schema_migrations의 version/checksum으로 중복 적용과 적용된 파일의 변경을 감지한다.
- migration도 전용 advisory lock으로 직렬화한다. 적용과 버전 기록을 같은 트랜잭션으로 처리하며 실패한 버전은 기록하지 않는다.
- 새 DB에서는 migration → seed → API 검증을 수행한다. 기존 Docker 볼륨에도 migration을 적용하며 볼륨 삭제로 대체하지 않는다.
- Compose는 common과 frontend/public을 읽기 전용으로 연결하고 COMMON_DIR와 FRONTEND_PUBLIC_DIR을 전달한다. backend 단독 이미지에서는 별도 마운트가 필요하다.
- 이미지는 frontend/public에서 제공한다. seed의 실제 파일 검증은 리포지토리의 사전 검증 또는 읽기 전용 경로를 통해 수행한다. 백엔드는 이미지를 직접 배포할 필요가 없다.
- 명령과 테스트 방법은 [DB 실행 안내](../backend/app/db/README.md)를 따른다. 현재 개발 DB에 migration/seed를 적용했으며 별도 테스트 스키마에서 PostgreSQL 통합 테스트 5개를 통과했다.

## 8. 완료 조건

- 새 seed 결과는 메뉴 11개·온도 16행이고 카테고리·가격이 common과 일치한다. 고유 이미지 14개가 모두 존재한다.
- 재실행해도 중복 행이 없고 기존 주문과 판매/표시 설정이 유지된다.
- 터치 주문 번호가 DB 행과 일치하며 잘못된 메뉴·온도·판매 중지 요청으로 주문이 생성되지 않는다.
- 카탈로그 갱신과 주문이 동시에 발생해도 잠금 시점의 일관된 이름·가격·온도로 저장한다.
- 카탈로그 변경 후에도 과거 주문 스냅샷이 유지된다.
- DB 실패·응답 불명확을 성공으로 표시하지 않는다. 같은 UUID의 동시 요청과 재전송은 주문 한 건과 같은 번호를 반환한다.
- 추천·관리·음성 테이블은 후속 migration에서 별도로 설계한다.
