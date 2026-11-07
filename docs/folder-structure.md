# 폴더 구조

```text
Hackaton/
├── frontend/              # React + Vite + TypeScript 화면
│   ├── src/
│   │   ├── main.tsx      # 앱 마운트와 공통 스타일
│   │   ├── App.tsx       # 시작/주문 화면 전환
│   │   ├── screens/      # StartScreen, OrderScreen, order/ 단계별 화면
│   │   ├── components/   # 브랜드 로고, 메뉴 카드, 마이크 아이콘
│   │   │   ├── layout/  # KioskLayout, OrderGuide, OrderFooter와 전용 CSS
│   │   │   ├── voice/   # MicrophoneButton과 전용 CSS
│   │   │   └── menu/    # MenuBoard와 전용 CSS
│   │   ├── api/          # 공통 계약, HTTP/mock 어댑터, 오류, 실행 설정
│   │   ├── hooks/        # 메뉴 로딩과 비동기 주문 제출
│   │   ├── state/        # 주문 단계와 옵션 전이 (orderReducer)
│   │   ├── data/         # common을 참조하는 화면용 메뉴 어댑터
│   │   └── styles/       # 공통 스타일과 반응형 레이아웃
│   ├── public/images/    # 공식 브랜드 로고와 메뉴 이미지
│   ├── package.json       # 프론트엔드 의존성 및 실행 명령
│   ├── vite.config.ts     # 개발 서버 및 API 요청 전달 설정
│   └── Dockerfile         # 프론트엔드 실행 환경
├── common/                # 메뉴·가격·이미지·브랜드 기준 데이터
├── backend/               # Python + FastAPI 서버
│   ├── app/main.py        # API 진입점 및 DB 연결 상태 확인
│   ├── requirements.txt   # 백엔드 의존성
│   ├── .env               # 로컬 API 키 등 환경변수 (Git 제외)
│   └── Dockerfile         # 백엔드 실행 환경
├── docs/                  # 기획, 아키텍처, API 및 DB 설계 문서
├── compose.yaml           # 프론트엔드·백엔드·PostgreSQL 실행 설정
├── .gitignore             # Git에서 제외할 파일 설정
└── README.md              # 개발 환경 설치 및 실행 안내
```

- 화면 수정은 `frontend/src/`, API 구현은 `backend/app/`에서 진행합니다.
- 화면은 API 어댑터를 사용하고, 기본 mock 어댑터가 common 데이터를 참조합니다. Docker Compose는 common을 `/common`에 읽기 전용으로 연결하고 public 자산도 마운트합니다. Compose 설정 변경 후 `docker compose up -d`로 반영하세요.
- 현재 화면은 시작·메뉴 조회·확대·옵션 선택·최종 확인·개발용 완료까지 제공합니다. 실제 주문 저장 API·DB 저장·음성 입력은 후속 구현입니다.
- 주문 단계 화면은 `KioskLayout`에 제목·안내·상태·마이크 영역과 중앙 `children`을 전달합니다. 메뉴 선택·확대 상태는 `OrderScreen`이 관리하고, 공통 레이아웃은 화면별 주문 상태를 관리하지 않습니다. 마이크 비활성화 사유는 `MicrophoneButton`의 `helpText`로 표시합니다.
- DB 데이터는 Docker 볼륨에 저장됩니다.
- `.env`는 각자 로컬에서 생성하며, 현재 Docker 환경변수 로딩과 OpenAI 호출 연결은 별도 구현이 필요합니다.

- 간편/전체 목록과 확대 상태는 OrderScreen이 독립적으로 보유하고 MenuBoard에 전달합니다. 간편 목록은 common/menu_display.json에서 관리합니다.

- components/order/OrderSummary는 선택 메뉴·온도별 이미지·가격·옵션을 표시합니다. screens/order/OrderFlow.css에서 단계별 화면 스타일을 관리합니다. frontend/tests/order.test.mjs는 주문 상태 전이를 검증합니다.
