# 카페 키오스크 — 팀원용 개발 환경 안내

처음 사용하는 팀원은 **1번부터 순서대로** 따라 하면 됩니다.
이미 설치와 첫 실행을 마쳤다면 **5번 ‘매일 개발할 때’**만 보면 됩니다.

## 1. 무엇을 실행하나요?

명령어 하나로 아래 세 가지를 함께 실행합니다.

| 구성 | 역할 |
| --- | --- |
| React + Vite + TypeScript | 브라우저에서 보는 화면 |
| Python + FastAPI | 화면의 요청을 받아 처리하는 서버 |
| PostgreSQL | 데이터를 저장하는 DB |

Docker는 이 프로그램들을 정해진 환경에서 실행해 주는 도구입니다. Docker Compose는 세 프로그램을 한 번에 켜고 연결해 줍니다.

**현재는 화면 → 백엔드 → DB 연결을 확인하는 기본 환경입니다. 메뉴·주문·추천 기능과 Whisper 실행·학습 환경은 아직 포함하지 않습니다. 지금 실행에는 GPU가 필요 없습니다.**

## 2. 처음 한 번 설치하기

- [Git](https://git-scm.com/downloads): 팀의 코드를 내 컴퓨터로 받는 도구입니다.
- [Docker Desktop](https://www.docker.com/products/docker-desktop/): 개발 환경을 실행하는 프로그램입니다.
- 코드 편집기: VS Code 등 원하는 편집기를 사용하세요.

Windows에서는 Docker Desktop의 WSL 2 기반 Linux 컨테이너 환경을 사용하세요. 설치 중 WSL 설치·업데이트나 재부팅을 요청하면 화면 안내를 따라 진행하세요. [Windows 공식 설치 안내](https://docs.docker.com/desktop/setup/install/windows-install/)

Mac에서는 내 컴퓨터의 칩 종류에 맞는 Docker Desktop을 설치하세요. 이후 아래 실행 명령은 같습니다.

**Docker로 실행하기 위해 Node.js, Python, PostgreSQL을 PC에 따로 설치할 필요는 없습니다.** 편집기의 자동완성 등에는 추가 설정이 필요할 수 있습니다.

설치 후 Docker Desktop을 열고 엔진이 실행될 때까지 기다리세요. 터미널을 새로 열어 확인합니다.

```sh
git --version
docker --version
docker compose version
```

버전이 출력되면 명령어를 사용할 준비가 된 것입니다. 실제 컨테이너를 켜려면 Docker Desktop도 실행 중이어야 합니다.

> 터미널 여는 방법: Windows는 PowerShell, Mac은 터미널 앱을 사용하세요. VS Code에서는 상단 메뉴의 ‘터미널 → 새 터미널’을 선택하면 됩니다. 아래 명령은 한 줄씩 입력하고 Enter를 누르세요. `PS C:\...>` 같은 프롬프트는 입력하지 않습니다.

## 3. 프로젝트 코드 받기

코드를 보관할 폴더에서 다음 명령을 실행하세요.

```sh
git clone https://github.com/47Foden/Hackaton.git
cd Hackaton
```

GitHub 로그인이 필요하면 안내에 따라 로그인하세요. 접근 권한 오류가 나면 저장소 초대를 수락했는지 확인하세요.

**이미 코드를 받았다면 다시 clone하지 마세요.** 기존 `Hackaton` 폴더를 편집기로 열고 그 폴더에서 터미널을 열면 됩니다.

터미널의 현재 위치에 다음 파일이 있어야 합니다.

```text
Hackaton/
├── compose.yaml
├── README.md
├── frontend/
└── backend/
```

이후 안내하는 모든 명령은 **compose.yaml이 있는 Hackaton 폴더**에서 실행하세요. 내 컴퓨터의 저장 위치는 다른 팀원과 달라도 됩니다.

## 4. 처음 실행하기

Docker Desktop이 켜져 있는지 확인한 뒤 실행하세요.

```sh
docker compose up -d --build --wait
```

첫 실행은 필요한 파일과 라이브러리를 내려받으므로 몇 분 걸릴 수 있습니다. 터미널에 글자가 계속 나오는 것은 정상입니다.

| 옵션 | 뜻 |
| --- | --- |
| `up` | 서비스를 실행합니다. |
| `-d` | 터미널을 계속 사용할 수 있게 뒤에서 실행합니다. |
| `--build` | Dockerfile에 적힌 환경을 만듭니다. |
| `--wait` | 서비스가 준비될 때까지 기다립니다. |

명령이 오류 없이 끝났다면 브라우저에서 아래 주소를 여세요.

| 확인할 것 | 주소 | 정상 결과 |
| --- | --- | --- |
| 프론트 화면 | [http://localhost:5173](http://localhost:5173) | ‘프론트 · 백엔드 · DB 연결 완료’ 표시 |
| API 문서 | [http://localhost:8000/docs](http://localhost:8000/docs) | API 목록과 테스트 화면 |
| DB 연결 확인 | [http://localhost:8000/api/health](http://localhost:8000/api/health) | `{"status":"ok","database":"connected"}` |

**프론트 화면에 연결 완료가 나오면 개발을 시작할 준비가 끝난 것입니다.**

`localhost`는 ‘내 컴퓨터’라는 뜻입니다. 이 주소를 다른 사람에게 보내도 내 화면에 접속하는 것이 아닙니다. 각자 Docker를 실행해야 합니다.

## 5. 매일 개발할 때

### 개발 시작

1. Docker Desktop을 켭니다.
2. 편집기로 프로젝트를 열고 터미널을 엽니다.
3. 다음 명령을 실행합니다.

```sh
docker compose up -d
```

4. 브라우저에서 [http://localhost:5173](http://localhost:5173)을 엽니다.
5. 코드를 수정하고 저장합니다.

| 작업 | 처음 수정할 파일 |
| --- | --- |
| 화면 만들기 | `frontend/src/main.tsx` |
| API 만들기 | `backend/app/main.py` |

**코드는 내 컴퓨터의 편집기에서 수정하세요. 컨테이너 안에 들어갈 필요가 없습니다.** `frontend/src`와 `backend/app`의 변경 사항은 자동 반영되도록 연결되어 있습니다. 보통의 화면·API 수정마다 Docker를 다시 빌드하지 않아도 됩니다.

### 개발 종료

```sh
docker compose stop
```

서비스만 멈추며 코드와 DB 데이터는 남습니다. 터미널 창만 닫는 것으로는 컨테이너가 종료되지 않습니다.

## 6. 팀원의 변경 사항을 받았을 때

먼저 내 작업 상태를 확인하세요.

```sh
git status
```

내가 수정 중인 파일이 있다면 먼저 커밋하거나 따로 보관한 뒤 팀의 작업 브랜치에서 최신 코드를 받으세요. 변경 사항을 버리면서 진행하지 마세요.

```sh
git pull
docker compose up -d --build --wait
```

Dockerfile이나 라이브러리 목록이 바뀌었어도 재빌드하면 반영됩니다. 바뀐 것이 없으면 기존 빌드 결과를 재사용합니다.

## 7. 자주 쓰는 명령 모음

| 할 일 | 명령 |
| --- | --- |
| 시작 | `docker compose up -d` |
| 첫 실행 / 환경 변경 반영 | `docker compose up -d --build --wait` |
| 실행 상태 확인 | `docker compose ps` |
| 전체 로그 확인 | `docker compose logs --tail=100` |
| 백엔드 로그 계속 보기 | `docker compose logs -f backend` |
| 프론트 로그 계속 보기 | `docker compose logs -f frontend` |
| 종료 | `docker compose stop` |
| 컨테이너와 네트워크 정리 | `docker compose down` |

로그 보기에서 `Ctrl+C`를 누르면 로그 보기만 종료됩니다. 백그라운드 서비스는 계속 실행됩니다.

**`docker compose down`도 DB 데이터는 유지합니다. 반면 `docker compose down -v`는 DB 저장 공간까지 삭제하므로 일반적인 종료에 사용하지 마세요.**

## 8. 안 될 때 확인하기

| 증상 | 해결 방법 |
| --- | --- |
| `docker` 명령을 찾을 수 없음 | Docker Desktop 설치 후 터미널을 다시 여세요. |
| Docker 엔진 연결 오류 / `Cannot connect` | Docker Desktop을 켜고 실행 준비가 끝날 때까지 기다리세요. |
| WSL 관련 오류 | Docker Desktop 안내에 따라 WSL 설정·업데이트를 완료하고 필요하면 재부팅하세요. |
| `no configuration file provided` | 현재 폴더에 `compose.yaml`이 있는지 확인하세요. 보통 `cd Hackaton`이 필요합니다. |
| `port is already allocated` / `address already in use` | 5173 또는 8000 포트를 다른 프로그램이 쓰고 있습니다. 해당 프로그램을 종료하거나 아래 방법으로 포트를 바꾸세요. |
| 이미지나 라이브러리 다운로드 실패 | 인터넷 연결을 확인한 뒤 첫 실행 명령을 다시 실행하세요. |
| `unhealthy` 표시 | `docker compose logs --tail=100 backend db`로 오류 내용을 확인하세요. |
| 화면이 안 열림 | `docker compose ps`로 실행 상태를 확인하고 주소가 `http://localhost:5173`인지 확인하세요. |
| 화면은 열리는데 연결 실패 | `docker compose logs --tail=100 backend frontend`로 오류를 확인하세요. |

포트가 겹치면 `compose.yaml`의 프론트 포트 설정에서 아래처럼 **내 컴퓨터 쪽 포트만** 바꿀 수 있습니다.

```yaml
# 기존
- "127.0.0.1:5173:5173"
# 변경 예시
- "127.0.0.1:5174:5173"
```

수정 후 `docker compose up -d`를 실행하고 `http://localhost:5174`로 접속하세요. 컨테이너 쪽 마지막 숫자는 그대로 둡니다.

해결되지 않으면 **실행한 명령 + 오류 메시지 + `docker compose ps` 결과**를 팀에 공유하세요. 비밀키가 포함된 설정 파일은 공유하지 마세요.

## 9. 알아두면 좋은 점

### DB는 각자의 컴퓨터에 따로 있습니다

Docker는 실행 환경을 맞춰 주지만 DB 데이터를 팀원끼리 자동 공유하지는 않습니다. 한 사람이 메뉴 데이터를 넣어도 다른 사람의 DB에는 생기지 않습니다. 공통 메뉴 데이터는 나중에 초기 데이터 파일 등으로 함께 관리합니다.

DB 데이터는 Docker의 별도 저장 공간인 볼륨에 보관됩니다. 현재 DB 계정은 로컬 개발용 예제이며 외부 배포에서 재사용하지 않습니다.

### 라이브러리를 추가할 때

- 백엔드: `backend/requirements.txt`에 의존성과 버전을 기록합니다.
- 프론트: `frontend/package.json`과 `frontend/package-lock.json`을 함께 갱신합니다.
- 변경 후 `docker compose up -d --build --wait`로 다시 빌드합니다.

컨테이너 안에서 설치만 하고 파일에 기록하지 않으면 다른 팀원에게 전달되지 않고, 컨테이너를 다시 만들 때 사라질 수 있습니다.

### Docker 실행은 인터넷 배포가 아닙니다

현재 설정은 내 컴퓨터에서 개발하는 용도이며 앱 포트는 로컬 접속만 허용합니다. Vercel 등으로 공개하려면 별도 배포 설정이 필요합니다.

### Whisper는 별도로 추가합니다

GPU 종류와 메모리, 실행 OS를 확인한 뒤 모델 실행·학습 환경을 추가합니다. 현재 명령을 실행한다고 Whisper가 설치되거나 학습되지는 않습니다. 모델 파일과 녹음 원본은 Git에 넣지 않습니다.

## 10. 필요한 사람만 보는 추가 명령

백엔드 컨테이너 안에서 명령을 실행하고 싶을 때:

```sh
docker compose exec backend sh
```

`exit`를 입력하면 나옵니다. 컨테이너는 계속 실행됩니다.

프론트 타입 검사와 배포용 파일 생성:

```sh
docker compose exec frontend npm run build
```

결과는 컨테이너의 `/app/dist`에 생성됩니다.

DB에 직접 접속:

```sh
docker compose exec db psql -U kiosk -d kiosk
```

`\q`를 입력하면 나옵니다. DB 포트는 내 컴퓨터에 공개하지 않았으므로 이 명령으로 접속합니다.

### 개발 환경의 요청 흐름

```text
브라우저 localhost:5173
  → Vite가 /api 요청 전달
  → backend:8000 (FastAPI)
  → db:5432 (PostgreSQL)
```

컨테이너끼리는 `backend`, `db`라는 이름으로 접속합니다. 브라우저는 이 이름을 모르므로 화면 코드에서는 `/api` 경로를 사용합니다. Vite의 개발용 요청 전달 설정은 배포용 정적 파일에 포함되지 않으므로, 외부 배포 시에는 실제 백엔드 주소와 요청 전달 또는 CORS 설정이 필요합니다.

참고: [Docker Compose 공식 시작 가이드](https://docs.docker.com/compose/gettingstarted/)
