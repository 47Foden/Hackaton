# 카페 키오스크 개발 환경

React + Vite + TypeScript, Python + FastAPI, PostgreSQL을 Docker Compose로 함께 실행합니다.
현재는 연결 확인용 시작 화면과 API만 있습니다. 메뉴·주문·Whisper 모델·학습 코드는 아직 포함하지 않습니다.

## 준비

각 팀원은 Git과 Docker Desktop을 설치하고 Docker Desktop을 실행하세요.
Windows에서는 WSL 2 기반 Linux 컨테이너를 사용하세요.
Docker를 통해 실행할 때 PC에 Node.js, Python, PostgreSQL을 별도로 설치할 필요는 없습니다.
편집기의 자동완성 등을 위해 로컬 개발 도구를 추가 설치할 수는 있습니다.

## 첫 실행

이 README와 compose.yaml이 있는 폴더에서 터미널을 열고 실행하세요.

```powershell
docker compose up -d --build --wait
```

처음에는 이미지와 라이브러리를 내려받아 시간이 걸립니다.

- 화면: http://localhost:5173
- API 문서: http://localhost:8000/docs
- DB까지 연결 확인: http://localhost:8000/api/health

## 파일 역할

- `frontend/Dockerfile`: Node.js와 프론트 라이브러리를 설치하고 Vite를 실행합니다.
- `backend/Dockerfile`: Python과 백엔드 라이브러리를 설치하고 FastAPI를 실행합니다.
- `compose.yaml`: 두 앱과 PostgreSQL을 함께 실행하고 포트·연결·저장 공간을 설정합니다.
- `frontend/src/main.tsx`: 화면을 수정하는 시작 파일입니다.
- `backend/app/main.py`: API를 추가하는 시작 파일입니다.

Dockerfile은 이미지를 만드는 설명서, 이미지는 실행 환경의 묶음, 컨테이너는 그 이미지를 실행한 상태입니다.
Compose는 여러 컨테이너를 한 번에 관리하는 도구입니다.

## 평소 개발

코드는 PC의 편집기에서 수정하세요. frontend/src와 backend/app은 컨테이너와 연결되어 있어 저장하면 자동 반영됩니다.
Windows에서도 파일 변경을 감지하도록 polling을 켰습니다.
컨테이너 안에 들어가서 코드를 직접 수정할 필요가 없습니다.

```powershell
docker compose up -d
docker compose ps
docker compose logs -f backend
```

로그 보기에서 Ctrl+C를 눌러도 백그라운드 서비스는 계속 실행됩니다.
개발을 마쳤을 때:

```powershell
docker compose stop
```

컨테이너와 네트워크까지 정리할 때:

```powershell
docker compose down
```

둘 다 DB 데이터는 named volume에 유지됩니다. `docker compose down -v`는 DB 저장 공간까지 삭제하므로 초기화하려는 경우에만 사용하세요.
팀원별 로컬 DB는 서로 별개이며 Docker가 데이터를 자동 공유하지는 않습니다.

## 라이브러리 또는 설정 변경

Python 라이브러리는 backend/requirements.txt에 기록한 뒤 재빌드합니다.
프론트 라이브러리는 package.json과 package-lock.json을 함께 갱신합니다.
컨테이너 안에서 임시로 설치만 하면 재생성 시 사라질 수 있습니다.

```powershell
docker compose up -d --build --wait
```

Dockerfile, 의존성 목록, Compose 설정을 바꿨을 때 위 명령을 사용하세요.
일반적인 화면/API 소스 수정에는 재빌드가 필요 없습니다.

## 컨테이너 안에서 명령 실행

```powershell
docker compose exec backend sh
```

`exit`로 나오세요. 컨테이너 자체는 종료되지 않습니다.

프론트 배포 파일 생성 및 타입 검사:

```powershell
docker compose exec frontend npm run build
```

DB 접속:

```powershell
docker compose exec db psql -U kiosk -d kiosk
```

`\q`로 나옵니다.

## 연결 구조와 배포

브라우저 → localhost:5173 → Vite의 /api 프록시 → backend:8000 → db:5432

컨테이너끼리는 backend, db라는 서비스 이름으로 접속합니다.
브라우저는 이 이름을 모르므로 화면에서는 /api 경로를 사용합니다.
DB는 호스트 포트를 공개하지 않았고 앱은 이 PC의 localhost에서만 접근할 수 있습니다.
DB 계정은 로컬 개발 전용 예제이며 외부 배포에서 재사용하지 마세요.

이 구성은 자동 새로고침이 켜진 개발 환경이며 인터넷 배포가 아닙니다.
Vercel에 프론트를 배포할 때는 실제 백엔드 주소와 프록시 또는 CORS 설정을 따로 구성해야 합니다.
Vite 개발 프록시는 빌드된 정적 파일에 포함되지 않습니다.

## Whisper 추가 시

GPU 종류, GPU 메모리, 실행 OS를 확인한 뒤 모델용 이미지와 GPU 설정을 추가합니다.
일반 Python 이미지에 PyTorch만 설치한다고 GPU가 자동으로 연결되지는 않습니다.
학습은 별도 작업으로 실행하고, 서비스에는 완료된 모델을 불러오도록 구성합니다.
모델 파일과 녹음 원본은 Git에 넣지 마세요.

## 문제 해결

- Docker 연결 오류: Docker Desktop이 실행 중인지 확인하세요.
- 포트 충돌: compose.yaml에서 왼쪽의 5173 또는 8000을 비어 있는 포트로 바꾸고 다시 실행하세요.
- 첫 실행 실패: 인터넷 연결과 `docker compose logs`를 확인하세요.
- 화면은 뜨는데 API 실패: `docker compose ps`와 `docker compose logs backend`를 확인하세요.

공식 안내: https://docs.docker.com/compose/gettingstarted/
