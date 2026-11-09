# LLM 직접 추천 텍스트 실험

공유 기준선은 **v1(개선 전)**이며, 별도 **[v2 구현 초안](experiments/v2-design.md)**을 추가했다. v2 실제 API 성능은 아직 미평가다. [버전 기록](experiments/versions.md)에 따라 별도 커밋과 새 결과 폴더로 구분한다.

첫 실제 실험(2026-11-09)의 [검토 결과](experiments/2026-11-09-first-live/review.ko.md), [실행 결과](experiments/2026-11-09-first-live/results.ko.md), [원본 JSON](experiments/2026-11-09-first-live/results.json)을 함께 보관한다. 현재 결과는 기존 방식보다 낫다는 근거가 아니며 운영 기본값은 유지한다.

## 키 소유자가 직접 실행하는 첫 소규모 유료 실험

`backend/.env`에 키를 저장한 뒤 키 소유자가 본인 터미널에서 실행한다. 키를 채팅/보고서/Git에 넣지 않는다. 이 모듈은 기본 mock 모드에서 키 파일을 열지 않으며 live에서만 python-dotenv로 키 한 항목을 읽는다. `${...}` 보간은 비활성화한다. 기존 backend 의존성에 python-dotenv가 포함돼 있다.

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -B -m app.experiments.run_small_experiment --mode live --allow-paid-api --env-file backend/.env --rates 0.75 0.075 4.5 --output-dir work/first-live
```

이 명령은 로컬 `/api/menus`를 읽고 검증된 근거를 합친 뒤 연결 확인 1회, 성공 시 다섯 발화 각 1회(최대 6회)를 호출한다. 연결 확인 오류면 후속 호출은 하지 않는다. 자동 재시도는 없고 기존 결과 파일이 있으면 같은 폴더에 재실행하지 않는다. 모델은 `gpt-5.4-mini-2026-03-17`, reasoning none, max_output_tokens 1800이다. 계정에서 모델을 사용할 수 있는지는 실제 호출 전까지 보장하지 않는다.

연결 확인에서 HTTP/인증은 성공했지만 후보가 가격 등 검증을 위반해 중단될 수도 있다. 이때 결과는 실패 실험으로 보존한다. `--resume-report work/first-live/results.json`을 위 명령에 추가하고 새 output-dir을 지정하면 원래 메뉴 스냅샷과 연결 확인 응답을 재사용하고 다섯 발화만 새로 호출한다. HTTP/인증/잘림 등 유효 응답을 받지 못한 실패는 이 방법으로 재개할 수 없다. 이미 비교까지 수행한 보고서도 재개할 수 없다. 키 파일은 재개할 때도 소유자 본인 프로세스만 읽는다.

단가는 [공식 모델 문서](https://developers.openai.com/api/docs/models/gpt-5.4-mini)의 2026-11-09 확인 기준, 백만 토큰당 입력/캐시 입력/출력 USD 0.75/0.075/4.50이다. 실행 전 요금을 다시 확인한다. 위 단가는 명령에서 지정하며 사용량으로 비용을 추정한다. 총 결제 한도를 강제로 보장하는 기능은 아니다.

`results.ko.md`와 `results.json`에는 결과·거부된 구조화 응답·usage·비용·한계가 남는다. 키나 HTTP 인증 헤더는 저장하지 않는다. 서버에서 거부된 후보는 정상 추천과 구별해 분석하며 운영에 사용하지 않는다. 기존 추천과 자료의 차이, 한 번씩 실행해 반복 일관성을 측정하지 못한 점도 기록한다. 팀 공유 시 이 결과 파일만 검토하며 .env를 열거나 첨부하지 않는다. 빌린 키는 소유자가 허용한 범위 안에서만 사용한다.

기존 기본값(Whisper → 규칙 해석 → Pretuning CSV 정렬)은 그대로다. 새 모듈은 웹/음성 라우터에 연결하지 않는다. LLM에는 전사 텍스트와 실제 메뉴 정보를 제공하고 **후보 선택과 순서까지** 맡긴다. 매 요청 맛 점수표 생성이나 기존 점수 재정렬을 하지 않는다.

## 지금 가능한 무료 검증

저장소 루트 PowerShell, Python 3.11 이상:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -m unittest discover -s backend/tests -p test_llm_direct.py -v
python -m unittest discover -s backend/tests -p test_recommendation.py -v
```

직접 추천 테스트는 표준 라이브러리만 사용한다. 기존 11개 메뉴의 실제 ID/가격/온도를 읽되 테스트 판매 여부는 합성값이다. 테스트에는 네트워크/API 키가 필요 없다. mock은 고정 `insufficient_data` 응답이며 언어 해석·추천 성능을 재현하지 않는다. 일관성/지연도 실제 LLM 성능으로 해석하면 안 된다.

DB 메뉴로 비교하려면 기존 백엔드 의존성 및 DB 설정이 필요하다. `.env`는 자동으로 읽지 않으므로 기존 backend 컨테이너 실행이 편리하다:

```powershell
docker compose exec backend python -m app.experiments.compare_recommendations --mode mock --repeat 3 --output /tmp/llm-comparison-mock.json
```

컨테이너가 이전 이미지라 새 모듈이 포함돼 있지 않을 수 있다. 팀 Dockerfile/compose를 수정할 필요는 없다. 저장소 밖 프론트 override는 이 실험에 필요하지 않다. 전체 `docker compose config`는 키를 노출할 수 있으므로 출력하지 않는다.

로컬에서 이미 저장한 `/api/menus` JSON 스냅샷(응답 객체 또는 메뉴 배열)으로도 실행할 수 있다:

```powershell
python -m app.experiments.compare_recommendations --menus work/menus.json --repeat 3 --output work/comparison-mock.json
```

파일의 판매 여부/가격/온도가 실제 DB에서 왔는지와 수집 시점을 별도로 확인한다. 저장소 seed만으로 현재 판매 중임을 간주하지 않는다. 보고서에는 메뉴 전체 스냅샷과 해시가 남는다. 실제 사용자 문장은 보고서에 기록되므로 공유 전에 확인한다.

## 자료와 검증 경계

현재 DB에는 검증된 맛·재료·카페인·알레르기 설명 필드가 없다. 기본 `verified_facts`는 빈 배열이다. 이름/카테고리로 무우유·무카페인 등을 확정하지 않는다. 공식 레시피, 성분표, 카페인 함량과 온도별 설명이 필요하다. 가격 출처/메뉴명 별칭 한계는 `common/README.md`와 `common/recommendation/README.md`를 따른다.

검토한 자료만 별도 JSON `--facts work/verified-facts.json`으로 제공한다. 형식은 `menu_id -> [{"text": "확인한 설명", "source": "자료 URL 또는 문서 식별자", "checked_date": "YYYY-MM-DD"}]`이다. 가상 설명을 넣지 않는다. 출처 필드는 사람이 확인해야 하며 프로그램이 출처의 진실성을 입증하지는 않는다. DB에 임의로 추가한 설명 필드는 자동 전송하지 않는다.

서버는 구조, ID/중복, 판매 여부, 가능한 온도, 선언한 예산/온도/카테고리·ID 제외를 검사한다. 위반하면 결과 전체를 거부한다. 우유·카페인 제외는 기계 검증 가능한 자료가 없으므로 후보를 거부하고 자료 요청/질문 응답만 허용한다. 결과를 기존 점수로 보정하지 않는다. 자유문장 전체의 조건 추출·의미·근거 정확성을 서버가 보장하지는 않는다. 프롬프트는 사용자 문장과 메뉴 자료를 데이터로 격리하지만 프롬프트 주입 방어가 완전하다는 주장은 하지 않는다.

기본 다섯 발화에는 사람이 작성한 `constraints` 주석이 있다. 이 주석은 서버 검증에만 사용하며 LLM에는 전송하지 않는다. LLM은 원문에서 조건을 이해하고 후보를 직접 선택해야 한다. 기존 추천 함수도 변경하지 않는다. 임의 발화는 `[{"id":"unique-id","text":"사용자 문장","constraints":{}}]`로 추가한다. 지원 주석 키: `max_price_krw`, `temperature`, `excluded_menu_ids`, `excluded_categories`, `unverified_exclusions`. 사람 평가와 서버가 검증한 제한의 범위를 함께 기록한다. 이전 버전의 mock 보고서는 LLM 요청에 주석을 포함했으므로 현재 결과와 구별한다.

API 없이 공식 메뉴 근거를 점검하고 요청 미리보기를 만들려면 `common/experiments/llm_direct/README.md`를 따른다. 웹/Whisper를 수정하지 않고 `app.experiments.menu_evidence`로 동작한다. 준비한 공식 설명은 `--facts` 또는 준비된 `--menus` 파일로 명시적으로 제공해야 하며 자동으로 운영 메뉴에 반영되지 않는다.

## 나중에 실제 API 비교

**이번 구현/테스트에서는 유료 호출하지 않는다.** live는 기본 비활성이고 `--mode live --allow-paid-api --model <명시적으로 고른 모델>`을 모두 지정해야 한다. API 키는 `OPENAI_API_KEY` 환경변수로만 읽으며 출력하지 않는다. 모델의 Structured Outputs 지원 여부와 현재 요금을 실행 전에 확인한다. 구현 기준: [공식 OpenAI Structured Outputs 문서](https://developers.openai.com/api/docs/guides/structured-outputs).

향후 키/잔액 준비 후 위 mock 명령에 live 옵션을 적용한다. `--rates INPUT CACHED_INPUT OUTPUT`은 백만 토큰당 USD 단가 세 개다. 요금은 하드코딩하지 않는다. 미입력/usage 없음은 비용 `null`이며 0달러로 해석하지 않는다. 기존 방식 요청별 LLM 비용은 0이며 Pretuning 사전 생성 비용과 Whisper 비용은 제외한다. 시간은 메뉴 로딩을 제외한 함수 실행/HTTP/응답 검증 시간이다. timeout 45초, 자동 재시도 없음. HTTP 오류/거부/출력 잘림/형식 오류는 별도 코드로 기록한다. 실패 호출도 과금될 수 있어 usage 없는 실패의 비용은 미상이다.

## 평가

JSON에 각 실행의 결과, 지연, 토큰 usage, 비용 추정, 입력 차이, CSV 해시, 요청 예시, 반복별 순서 동일 여부와 전체 응답 종류 수를 기록한다. 각 `human_review`는 미평가 `null`이다. 사람이 조건 준수/적합성/근거 정확성을 0(실패), 1(부분), 2(충족)로 채우고 notes에 판단 근거와 질문의 적절성을 적는다. 자료가 없어 추천을 보류하는 경우와 잘못 확신하는 경우를 구별한다. 동일 후보 순서와 근거/질문의 일관성을 함께 본다. 오류 반복은 추천 일관성 성공으로 세지 않는다. mock 평가 점수는 작성하지 않는다.

DB 스냅샷은 실행 시작 시 한 번 읽으므로 실제 주문 시에는 판매 여부 재확인이 필요하다. 향후 충분한 실제 평가를 통과하면 별도 설정으로만 연결하고 기존 경로를 기본값으로 유지한다.
