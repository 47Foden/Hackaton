# 녹음 없이 추천 함수 시험

개발용 음성 주문 화면에서 ‘텍스트로 추천 시험’을 펼치면 기존 방식 또는 LLM v3를 선택할 수 있다. 기본은 기존 방식이며, 이 패널은 Vite 개발 모드에서만 보인다. 실제 녹음 경로는 아직 기존 추천을 사용한다.

## 서버 설정

- `LLM_TEXT_EXPERIMENT_ENABLED=1`인 서버에서만 LLM 텍스트 시험을 허용한다. 기본은 꺼짐이다.
- 서버 환경의 `OPENAI_API_KEY`를 사용하며 새 코드가 .env를 직접 읽거나 키를 프론트에 전달하지 않는다. 기존 Compose의 backend env_file을 그대로 사용한다.
- 모델은 `LLM_TEXT_MODEL`로 지정하며 기본은 기존 실험과 같은 `gpt-5.4-mini-2026-03-17`이다.
- 팀 compose.yaml을 수정하지 말고 개인용 외부 Compose override에서 backend.environment의 플래그와 모델만 추가한다. 전체 compose config 결과를 출력하지 않는다.

```yaml
services:
  backend:
    environment:
      LLM_TEXT_EXPERIMENT_ENABLED: "1"
      LLM_TEXT_MODEL: "gpt-5.4-mini-2026-03-17"
```

원래 Compose, 본인의 프론트 로컬 override, 위 backend override 순으로 지정해 컨테이너를 갱신한다. 명령 실행 시 Docker가 키 파일을 읽으며 assistant에게 키를 전달할 필요는 없다. 키 파일을 버전 관리하거나 화면에 붙여 넣지 않는다.

## API와 화면

- GET `/api/experiments/recommend-text`: LLM 활성화 여부, 키 설정 여부(bool), 모델, 기본/녹음 엔진을 반환한다. 키는 반환하지 않는다.
- POST 같은 경로: `transcript`, `engine`(기본 existing), `paid_call_confirmed`를 받는다. LLM은 유료 호출 확인이 true일 때만 진행한다.
- 기존 방식은 실제 DB 메뉴로 원래 recommendation.recommend를 호출한다. LLM 방식은 같은 DB 메뉴와 조사 근거로 llm_direct_v3.recommend를 실행한다. Whisper와 주문 명령 해석은 건너뛴 추천 함수 시험이다.
- 결과의 engine·모델·API 횟수와 후보·가격·온도·근거·질문/자료 부족·usage·응답시간·추정 비용을 표시한다.
- LLM 실행 버튼을 누를 때 실제 유료 API를 최대 1회 호출하며 자동 재시도나 기존 방식으로의 fallback은 없다. 동시에 진행 중인 LLM 요청이 있으면 추가 요청을 거부한다. 이 제한은 프로세스당이며 전체 서비스 사용량 상한은 아니다.
- ‘이 추천을 메뉴 선택 화면에 표시’는 후보 목록만 바꾸며 주문을 확정하지 않는다. 주문 옵션과 온도는 기존 주문 흐름에서 다시 확인한다.

화면에서 사용할 쉬운 예시: ‘레몬의 산미와 탄산이 있는 차가운 음료를 3,500원 이하로 추천해 주세요.’

## 검증과 한계

무료 API 테스트는 기본값, opt-in·키·유료 확인, 실제 v3 함수와 mock 공급자 연결, 조건 위반 거부, 질문/자료 부족 전달, 동시 요청 거부, 입력 검증, 안전한 오류 반환을 확인한다. 브라우저 검증은 합성 판매 상태와 mock 응답을 사용하며 실제 추천 성능이 아니다.

이 기능은 음성 인식이나 녹음 전체 주문 분기를 검증하지 않는다. 질문 이후 대화 메모리는 아직 없으며 원래 조건과 답을 합쳐 새 문장으로 입력해야 한다. 서비스의 음성 추천을 v3로 바꾸려면 별도 연결·설정 작업이 필요하다.

화면 응답시간은 DB 조회도 포함하며, 기존 CLI 실험의 함수/HTTP 시간과 직접 같은 지표로 비교하지 않는다. 비용은 기본 모델의 이전 확인 단가에 따른 추정이며 다른 모델이나 실패 호출의 비용은 미상일 수 있다. 실제 청구액을 보장하지 않는다.

[v1~v3 개발 과정과 실제 실험 결과](v1-v3-team-summary.ko.md)를 함께 참고한다.
