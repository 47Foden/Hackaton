# 폴더 구조

```text
Hackaton/
├── frontend/              # React + Vite + TypeScript 화면
│   ├── src/main.tsx       # 화면 진입점
│   ├── package.json       # 프론트엔드 의존성 및 실행 명령
│   ├── vite.config.ts     # 개발 서버 및 API 요청 전달 설정
│   └── Dockerfile         # 프론트엔드 실행 환경
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
- DB 데이터는 Docker 볼륨에 저장됩니다.
- `.env`는 각자 로컬에서 생성하며, 현재 Docker 환경변수 로딩과 OpenAI 호출 연결은 별도 구현이 필요합니다.
