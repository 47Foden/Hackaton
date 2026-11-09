# DB 실행 및 검증

명령은 저장소 루트에서 실행한다. 현재 PostgreSQL 17과 requirements.txt에 있는 psycopg를 사용하며 별도 ORM/라이브러리는 추가하지 않았다.

```sh
docker compose up -d db backend
docker compose exec -T backend python -m app.db.seed --check
docker compose exec -T backend python -m app.db.migrate
docker compose exec -T backend python -m app.db.seed
```

`--check`는 파일 검증만 하며 DB를 연결하거나 변경하지 않는다. migration과 seed는 명시적으로 실행한다. 앱 시작/health 요청에서 자동 실행하지 않는다. seed 실패가 테이블 미적용 때문이면 migration을 먼저 실행한다. 기존 볼륨을 삭제할 필요가 없다.

- connection.py: DATABASE_URL 연결. with 블록 성공 시 commit, 오류 시 rollback, 종료 시 close.
- migrations/: 순서가 고정된 SQL. 0001은 기본 주문 테이블, 0002는 주문 요청 UUID, 0003은 메뉴 분류와 온도별 옵션, 주문 옵션 스냅샷을 추가한다.
- migrate.py: ledger 생성, 체크섬 검증, advisory lock, 한 트랜잭션에서 미적용 migration 실행. 적용된 파일은 수정하지 않고 새 번호를 추가한다.
- catalog.py: common의 주문 카탈로그 JSON에서 메뉴 ID, 옵션 프로필, 가격·출처·온도별 이미지를 검증한다.
- seed.py: 검증 완료 후 한 트랜잭션으로 UPSERT. 같은 seed는 중복을 만들지 않으며 기존 판매/간편 목록 설정·주문을 유지한다. common에서 사라진 기존 메뉴는 자동 삭제하지 않고 중단한다.
- ../repositories/menus.py: list_menus()는 반복 읽기 격리 수준에서 일관된 메뉴 목록을 API 계약 형식으로 반환한다. read_menus(connection)은 호출자가 관리하는 연결에서 같은 조회를 수행한다. GET /api/menus 라우터에서 사용한다.

Docker Compose는 COMMON_DIR=/common, FRONTEND_PUBLIC_DIR=/frontend-public을 읽기 전용 마운트로 전달한다. 로컬 Python은 저장소의 common과 frontend/public을 기본으로 사용한다. 다른 환경에서는 두 환경변수로 위치를 지정한다. standalone backend 이미지만 사용할 때는 해당 디렉터리를 별도로 연결해야 한다.

## PostgreSQL 통합 테스트

개발 DB 연결 권한이 있는 상태에서 실행한다. 테스트는 UUID로 만든 전용 스키마만 사용하고 finally 성격의 tearDown에서 그 스키마를 제거한다. 개발 메뉴·주문 테이블은 건드리지 않는다.

PowerShell:

```powershell
$databaseTestsPath = (Resolve-Path backend/tests).Path
docker compose run --rm -T --no-deps -v "${databaseTestsPath}:/tests:ro" backend python -m unittest discover -s /tests -v
```

macOS/Linux:

```sh
docker compose run --rm -T --no-deps -v "$PWD/backend/tests:/tests:ro" backend python -m unittest discover -s /tests -v
```

검증 대상: migration 신규/반복 적용, 변경된 체크섬 거부, SQL 실패의 DDL/ledger 롤백, seed 반복과 기존 설정/주문 유지, common 가격/카테고리 매핑, 미등록 메뉴/누락 이미지/불리언 가격 거부, DB 제약과 연결 컨텍스트의 rollback. SQL 실행을 흉내 내는 mock 대신 실제 PostgreSQL을 사용한다.

API 통합 테스트는 메뉴 조회와 주문 저장을 검증한다. 주문 테스트는 요청 거부, 주문 스냅샷, 커밋 실패 시 롤백과 연결 해제, 동일 UUID 동시 요청과 내용 충돌을 확인한다.
