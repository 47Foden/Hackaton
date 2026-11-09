# 카페 키오스크 — 팀원용 개발 환경 안내

구현을 시작할 때: [3인 구현 첫날 계획 — 순서·분업·완료 기준](docs/plans/implementation-day1.md)

메뉴 DB 준비: [migration·seed 실행과 PostgreSQL 테스트](backend/app/db/README.md). 화면은 기본적으로 실제 메뉴를 조회하고, 주문 확정 시 PostgreSQL에 주문을 저장합니다. 개발용 mock 설정은 [프론트 API 안내](frontend/src/api/README.md)를 따릅니다.

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

### OpenAI API 키 설정

OpenAI 연동 개발 시 `backend/.env.example`을 같은 폴더의 `.env`로 복사하고 본인의 키를 입력합니다. VS Code에서 파일을 복사해 이름을 `.env`로 바꾸거나, 프로젝트 루트에서 실행하세요. 기존 `.env`가 있다면 덮어쓰지 않고 편집합니다.

```sh
# macOS / Linux / Git Bash (기존 파일을 덮어쓰지 않음)
cp -n backend/.env.example backend/.env
```

```powershell
# Windows PowerShell (기존 파일을 덮어쓰지 않음)
if (-not (Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

`backend/.env`를 열고 다음 변수에 키를 입력한 뒤 저장합니다.

```dotenv
OPENAI_API_KEY=여기에_본인의_API_키_입력
```

Docker Compose 2.24.0 이상에서는 `backend/.env`가 있으면 백엔드 컨테이너에 자동으로 전달합니다. 파일이 없어도 기본 연결 확인 기능은 실행됩니다. 키를 추가하거나 바꾼 뒤에는 백엔드를 다시 생성하세요.

```sh
docker compose up -d --force-recreate backend
```

키 값 대신 설정 여부만 확인하려면 다음 명령을 실행합니다.

```sh
docker compose exec backend python -c "import os; print('OPENAI_API_KEY 설정됨' if os.getenv('OPENAI_API_KEY') else 'OPENAI_API_KEY 미설정')"
```

`.env`는 Git에서 제외되며 Docker 이미지에도 복사하지 않습니다. 실제 키를 `.env.example`, 프론트 코드, `VITE_` 변수에 넣지 마세요. 현재 백엔드는 DB 연결 확인 API만 제공하므로, 이 설정은 키 전달을 준비하며 OpenAI API 호출 기능은 별도로 구현해야 합니다.

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

## 독립 음성 주문 모드

시작 화면의 **음성으로 주문하기**를 누르면 기존 터치 주문과 별도의 세션으로 시작합니다. 메뉴 확인 → 온도 → 추가 옵션 → 매장/포장 → 최종 확인 → 주문번호 순서입니다. 온도가 하나인 메뉴는 자동 선택하고, 추가 옵션은 화면에서 선택하거나 건너뜁니다. 마이크 시작과 선택 시 기존 안내를 중단하며 단계 이동 시 진행 중인 녹음을 해제하고 늦은 응답을 무시합니다. 인식 실패 시 재입력 안내와 터치 선택을 제공합니다.

기존 개발 DB에서 확장 카탈로그와 추가 옵션을 사용하려면 [DB 마이그레이션과 시드](backend/app/db/README.md)를 순서대로 실행하세요.

실제 음성 인식을 사용하려면 [전사 워커 실행 안내](docs/plan/voice-recommendation-integration.md)를 따라 Whisper 워커를 실행해야 합니다. Docker Desktop의 `backend/.env`에는 `VOICE_TRANSCRIPTION_URL=http://host.docker.internal:8765/transcribe`를 설정하고 `docker compose up -d --build --force-recreate backend frontend`로 반영합니다. 모델 가중치와 마이크 권한이 필요합니다. 전사 서버가 없으면 안내 및 터치 주문은 가능하지만 음성 선택은 사용할 수 없습니다.

`/api/voice/interpret`는 `menu_confirmation`과 `review` 단계에서 명시적인 긍정 발화를 `confirm`으로 반환합니다. 이 API 자체는 주문을 저장하지 않으며, 화면의 최종 확인 단계에서만 기존 주문 API를 호출합니다. 기존 요청 UUID 재시도 정책을 사용합니다.


### 로컬 전사 서버 기본 주소

Compose는 `backend/voice.env`의 `VOICE_TRANSCRIPTION_URL=http://host.docker.internal:8765/transcribe`를 기본으로 읽습니다. `backend/.env`가 있으면 그 값이 우선합니다. 실제 `.env`와 키는 Git에 올리지 않으며 `.env.example`만 공유합니다. 설정 변경 후 `docker compose up -d --force-recreate backend frontend`로 컨테이너를 다시 생성하세요. 주소 설정만으로 Whisper 워커가 시작되지는 않으므로 전사 워커도 별도로 실행해야 합니다.

### 음성 전사 서버에 연결하지 못하는 경우 (Windows + Docker Desktop)

이 메시지는 음성 정확도 문제가 아니라 백엔드에서 전사 워커에 접속하지 못했다는 뜻입니다. 모델 가중치·벤치마크 가상환경 설치 후 프로젝트 루트의 PowerShell에서 다음 두 명령을 각각 실행하고 워커 터미널을 유지하세요.

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
```

```powershell
& ./backend/scripts/voice/.venv/Scripts/python.exe -m app.services.voice.whisper_worker --model-dir models/whisper-large-v3-turbo --host 0.0.0.0 --port 8765
```

`Whisper worker ready`가 표시돼야 합니다. `0.0.0.0` 바인딩은 Docker에서 Windows 호스트로 접근하기 위한 설정입니다. 인증 없는 개발용 워커이므로 공용 네트워크에 노출하지 말고 방화벽에서 필요한 개발 네트워크만 허용하세요.

새 터미널에서 컨테이너→워커의 TCP 연결을 확인합니다. 이 검사는 음성 인식 결과까지 검증하지는 않습니다.

```powershell
docker compose exec backend python -c "import socket; s=socket.create_connection(('host.docker.internal',8765),timeout=5); s.close(); print('전사 워커 연결 성공')"
```

실패하면 워커 실행 여부, 포트, Windows 방화벽을 확인하세요. 화면은 녹음 종료 후 전사를 요청하며, 성공한 텍스트는 ‘인식한 말’로 표시합니다. 전사 문장은 보이는데 메뉴 선택이 안 되면 등록 메뉴명 일치 여부를 확인하세요. 일반 주문하기는 음성 기능 없이 동작합니다. 시작 화면의 자동 음성은 브라우저 재생 정책에 따라 차단될 수 있으며 ‘안내 다시 듣기’ 버튼으로 재생할 수 있습니다.

## 음성 추천

기존 11종 실험 결과는 제거했고 45종 점수표만 사용합니다. 현재 저장소에는 45종 `binary.csv`만 있으며, 학습 완료한 `continuous.csv`를 `common/recommendation/`에 넣기 전에는 추천 점수표 미준비를 안내합니다. 적용 방법은 [점수표 안내](common/recommendation/README.md)를 참고하세요.

음성 주문 모드에서 “달달한 음료”, “차갑고 달달한 티 종류 아무거나”, “덜 단 커피”, “단맛이 적은 음료”, “달지 않고 신맛 있는 음료”처럼 말한다. 등록 메뉴명에 먼저 정확히 일치하는지 확인하고, 취향이면 Pretuning의 CSV로 최대 4개를 추천한다. 후보가 적으면 가능한 수만 표시하고 없으면 재추천을 안내한다. 메뉴 이름이나 “첫 번째”, “2번”으로 선택할 수 있고 이후 메뉴 확인·온도·매장/포장·주문 확정까지 음성과 터치를 함께 사용할 수 있다. “다시 추천”, “재추천” 또는 다시 추천받기 버튼은 초기 음성 입력 화면으로 돌아간다.

명시된 맛 하나가 긍정이면 원점수 내림차순, 부정(안·덜·적·않·없·낮)이면 오름차순이다. 여러 맛은 각 부정 속성만 1-score로 반전한 뒤 동일 가중 평균을 내림차순으로 정렬한다. 맛 없이 종류나 추천만 요청하면 3가지 맛 평균을 사용하며 동점은 menu_id순이다. 종류·제공 온도·가격으로 먼저 필터링한다. 가격은 “3000원 이하/미만/이상/초과” 형태를 지원하며 학습 점수에 포함하지 않는다. 현재는 규칙 기반 한국어 해석으로 자유로운 모든 문장·이중 부정·복잡한 제외 조건을 지원하지 않는다.

데이터 출처와 메뉴명 매핑 한계는 common/recommendation/README.md를 참고한다. 카페인 정보가 없어 해당 조건은 안내 후 재입력을 요청한다. 추가 모델 호출은 없으며 기존 Whisper 전사 지연 자체를 줄이는 변경은 포함하지 않는다.
