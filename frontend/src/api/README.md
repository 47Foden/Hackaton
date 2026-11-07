# API 어댑터

기본 실행에서 GET /api/menus와 POST /api/orders는 Vite 프록시 → FastAPI → PostgreSQL을 사용한다. 주문 확정 버튼이 선택한 메뉴 ID·온도·이용 방식을 전송한다.

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
| VITE_ORDER_API_MODE | http | 주문 저장: http 또는 mock |
| VITE_API_MODE | 없음 | 이전 일괄 설정. 개별 모드가 지정되지 않았을 때 두 모드에 적용 |
| VITE_MOCK_SCENARIO | success | mock 기능의 실패 재현 |
| API_PROXY_TARGET | http://127.0.0.1:8000 | 로컬 Vite의 백엔드 주소. Docker는 http://backend:8000 |

개별 모드 → 이전 VITE_API_MODE → 기본값 순으로 적용한다. 기존 frontend/.env 또는 루트 .env에서 `mock`을 지정했다면 해당 값을 제거하거나 실제 연결에 사용할 개별 모드를 `http`로 설정한다.

로컬 Vite는 frontend/.env.example을 frontend/.env로 복사하고 서버를 재시작한다. Docker Compose는 루트 .env/실행 셸 환경변수를 전달하며 변경 후 docker compose up -d frontend로 반영한다. 프로덕션 번들은 빌드 시 설정을 사용하므로 재빌드한다. Vite 개발 프록시는 프로덕션 번들에 포함되지 않으며 배포 환경에서 /api 라우팅이 필요하다.

메뉴 DB가 준비되지 않았다면 다음을 먼저 실행한다.

```sh
docker compose up -d db backend frontend
docker compose exec -T backend python -m app.db.migrate
docker compose exec -T backend python -m app.db.seed
```

개발용 주문을 사용하려면 VITE_ORDER_API_MODE=mock을 지정한다. 이 모드는 화면에 DEV- 번호와 개발용 안내를 표시한다.

## 실패 재현

| VITE_MOCK_SCENARIO | 적용 범위 |
| --- | --- |
| success | 정상 mock 응답 |
| empty | 메뉴 모드 mock일 때 빈 목록 |
| menu-error | 메뉴 모드 mock일 때 조회 실패 |
| order-rejected | 주문 모드 mock일 때 명확한 거부 |
| order-uncertain | 주문 모드 mock일 때 접수 불명 |

실제 조회 모드에서는 menu-error/empty로 서버 응답을 덮어쓰지 않는다. HTTP 오류는 오류/재조회 UI로 표시한다. 지연·취소·불명확한 주문 결과를 처리하고, 접수 불명 상태에서는 자동 재전송하지 않는다.

단위 테스트는 `npm --prefix frontend test`, 타입 검사와 빌드는 `npm --prefix frontend run build`로 실행한다. 어댑터 테스트는 HTTP 응답을 주입해 실행한다.

## 화면 상태 브라우저 검증

frontend에서 `npx playwright install chromium`으로 테스트 브라우저를 설치한 뒤 `npm run test:e2e`를 실행한다. 테스트는 5177 포트의 전용 Vite 서버에서 HTTP 응답을 재현한다. `e2e/catalog.spec.mjs`는 메뉴 조회 상태와 이미지 대체 표시를, `e2e/order.spec.mjs`는 주문 확정 버튼의 POST 요청과 응답 표시를 검증한다.
