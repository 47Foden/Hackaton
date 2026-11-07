# API 어댑터

기본 실행은 **실제 메뉴 조회 + 개발용 주문**이다. GET /api/menus는 Vite 프록시 → FastAPI → PostgreSQL을 사용한다. POST /api/orders는 아직 서버에 없으므로 DEV- 번호를 반환하는 mock을 유지한다. 메뉴 조회 실패를 mock 카탈로그로 자동 대체하지 않는다.

- contracts.ts: 공통 요청·응답 계약.
- http.ts: HTTP 요청, 15초 제한, 오류 변환.
- createKioskApi.ts: 조회·주문 어댑터 조합. 개발용 주문은 조회한 메뉴 가격·판매 여부·제공 온도를 사용한다.
- mock/: 오프라인 카탈로그와 개발용 주문. 실제 저장·결제 없음.
- index.ts: 환경변수 해석과 앱 기본 API 인스턴스.
- ../hooks/: 조회/주문 비동기 상태와 취소 처리. 화면은 어댑터를 직접 선택하지 않는다.
- ../data/menuCatalog.ts: API 응답을 화면 모델로 변환.

## 설정

| 환경변수 | 기본값 | 의미 |
| --- | --- | --- |
| VITE_MENU_API_MODE | http | 메뉴 조회: http 또는 mock |
| VITE_ORDER_API_MODE | mock | 주문 저장: http 또는 mock |
| VITE_API_MODE | 없음 | 이전 일괄 설정. 개별 모드가 지정되지 않았을 때 두 모드에 적용 |
| VITE_MOCK_SCENARIO | success | mock 기능의 실패 재현 |
| API_PROXY_TARGET | http://127.0.0.1:8000 | 로컬 Vite의 백엔드 주소. Docker는 http://backend:8000 |

개별 모드 → 이전 VITE_API_MODE → 기본값 순으로 적용한다. 기존 frontend/.env 또는 루트 .env에 VITE_API_MODE=mock이 있다면 제거하거나 VITE_MENU_API_MODE=http를 지정해야 실제 조회한다.

로컬 Vite는 frontend/.env.example을 frontend/.env로 복사하고 서버를 재시작한다. Docker Compose는 루트 .env/실행 셸 환경변수를 전달하며 변경 후 docker compose up -d frontend로 반영한다. 프로덕션 번들은 빌드 시 설정을 사용하므로 재빌드한다. Vite 개발 프록시는 프로덕션 번들에 포함되지 않으며 배포 환경에서 /api 라우팅이 필요하다.

메뉴 DB가 준비되지 않았다면 다음을 먼저 실행한다.

```sh
docker compose up -d db backend frontend
docker compose exec -T backend python -m app.db.migrate
docker compose exec -T backend python -m app.db.seed
```

주문까지 실제 HTTP로 바꾸는 VITE_ORDER_API_MODE=http는 POST /api/orders 구현 이후 사용한다. UI의 개발용 번호/안내는 주문 모드로 결정한다.

## 실패 재현

| VITE_MOCK_SCENARIO | 적용 범위 |
| --- | --- |
| success | 정상 mock 응답 |
| empty | 메뉴 모드 mock일 때 빈 목록 |
| menu-error | 메뉴 모드 mock일 때 조회 실패 |
| order-rejected | 주문 모드 mock일 때 명확한 거부 |
| order-uncertain | 주문 모드 mock일 때 접수 불명 |

실제 조회 모드에서는 menu-error/empty로 서버 응답을 덮어쓰지 않는다. HTTP 오류는 오류/재조회 UI로 표시한다. 지연·취소·불명확한 주문 결과를 처리하고, 접수 불명 상태에서는 자동 재전송하지 않는다.

테스트: npm --prefix frontend test. 빌드: npm --prefix frontend run build. 어댑터 테스트는 별도 설정 주입으로 실행하며 실제 서버 검증과 구분한다. 프론트 컨테이너에서 실제 /api/menus 프록시를 거쳐 DB 메뉴 11개·온도 16개를 조회하고, 그 응답으로 DEV- 주문을 만드는 연결도 확인했다. 이 검증의 HTTP 호출은 메뉴 GET 한 번뿐이며 실제 주문을 저장하지 않았다.

## 화면 상태 브라우저 검증

frontend에서 npx playwright install chromium으로 테스트 브라우저를 설치한 뒤 npm run test:e2e를 실행한다. e2e/catalog.spec.mjs는 5177 포트의 전용 Vite 서버에서 API 지연·503·빈 목록과 이미지 404/빈 경로를 재현한다. 재조회 복구와 이미지 없이 옵션 선택까지 확인하며 실제 DB는 변경하지 않는다. 결과 파일은 test-results에 생성되고 Git에서 제외한다. 기존 npm test는 어댑터/상태 단위 테스트, npm run test:e2e는 실제 DOM/브라우저 동작 검증이다.
