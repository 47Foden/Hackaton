# API 어댑터

- `contracts.ts`: API 명세와 같은 snake_case 요청·응답, 공통 KioskApi 인터페이스.
- `http.ts`: /api/menus와 /api/orders를 호출. 15초 제한과 오류 변환. mock으로 자동 대체하지 않는다.
- `mock/`: common의 가격·이미지·간편 목록과 명세의 고정 ID/카테고리로 같은 계약을 반환. 메모리 안의 DEV- 번호이며 저장·결제 없음.
- `index.ts`: 실행 모드 선택. 기본 mock, VITE_API_MODE=http일 때만 실제 HTTP.
- `../data/menuCatalog.ts`: 응답을 화면용 모델로 변환하는 순수 함수.
- `../hooks/useMenus.ts`, `useOrderFlow.ts`: 비동기 로딩·오류·취소·제출을 화면 상태와 연결. JSX와 실제 통신 코드를 섞지 않는다.
- `../state/order.ts`: API 호출 없는 순수 상태 전이. 제출 성공 액션에서만 완료로 이동.

## 실행과 실패 재현

로컬 Vite는 frontend/.env.example을 frontend/.env로 복사해 설정하고 서버를 재시작한다. Docker Compose는 프로젝트 루트 .env 또는 실행 셸 환경변수 VITE_API_MODE / VITE_MOCK_SCENARIO를 전달한다. 변경 후 docker compose up -d frontend로 재생성한다. 프로덕션 번들은 빌드 시점 값을 사용하므로 다시 빌드해야 한다. 실제 HTTP는 서버 메뉴·주문 API 구현 후 사용하며, 현재는 health만 서버에 구현돼 있다.

| VITE_MOCK_SCENARIO | 화면 확인 |
| --- | --- |
| success | 메뉴 조회와 개발용 주문 완료, 기본값 |
| empty | 빈 메뉴 안내 |
| menu-error | 조회 오류와 다시 불러오기 |
| order-rejected | 명확한 주문 거부, 최종 확인 유지 및 재시도 가능 |
| order-uncertain | 접수 불명, 재전송 비활성화 |

개별 테스트는 createMockApi 옵션으로 지연/목록/실패를 주입한다. 위 시나리오는 고정 결과이므로 menu-error에서 재조회해도 오류가 유지된다. 설정을 success로 바꿔 재시작하면 복구된다. 네트워크 호출과 DB 저장은 발생하지 않는다.

처리 중 버튼과 처음으로를 비활성화한다. 요청 취소나 연결 단절이 서버 저장 취소를 보장하지 않으므로, 알 수 없는 결과는 자동 재전송하지 않는다. request_id 기반 서버 중복 방지는 후속이다.

테스트: npm --prefix frontend test. 타입 검사·빌드: npm --prefix frontend run build.
