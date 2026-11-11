# 브라우저 뒤로가기 및 추천 입력 검증 개선

검토 브랜치: `fix/taejun-navigation-input-guards`. 기준 main: `f6bbfcb`.

## 브라우저 화면 이동

기존 화면 전환은 React 상태만 변경하므로 브라우저 뒤로가기가 사이트의 이전 화면을 찾지 못했다. History API에 시작/주문/음성 화면과 주문 단계를 기록한다. 뒤로가기와 앞으로가기로 메뉴·온도·옵션·주문 확인을 복원하고 장바구니 수량 및 음성 추천/메뉴 확인 상태를 유지한다.

주문 전송 및 접수 여부 확인 중에는 이전 초안으로 돌아가지 않는다. 완료하거나 처음으로 이동해 종료한 세션은 다시 열지 않는다. 새로고침하면 새 주문을 시작한다. 사이트 진입 전 외부 방문 기록까지 막는 기능은 아니다.

변경 파일: `frontend/src/App.tsx`, `frontend/src/hooks/useKioskHistory.tsx`, `frontend/src/hooks/useOrderFlow.ts`, `frontend/src/screens/OrderScreen.tsx`, `frontend/src/screens/VoiceOrderScreen.tsx`, `frontend/e2e/browser-history.spec.mjs`.

## 추천 입력 검증

| 같은 입력/검증 | 수정 전 재현 결과 | 수정 후 |
|---|---|---|
| 레몬 말고 딸기 음료 추천해 주세요 | 두 맛을 동시에 요구하여 허용 후보 0개 | 딸기 선호와 레몬 제외 분리, 시험 자료에서 딸기 후보 5개 허용 |
| 레몬은 빼고 음료 추천해 주세요 | 의도적으로 주입한 레몬에이드 응답을 서버가 허용 | INELIGIBLE_OPTION으로 거부 |
| 3,00원 이하 추천 | ValueError가 메뉴 자료 오류 503으로 전파 | 미해석 금액으로 기록, mock 자료 부족 응답을 정상 전달 |
| -3000원 이하 추천 | 양수 3000원으로 해석 | 미해석 금액으로 기록 |

원하는 맛과 제외한 맛을 분리하고 검증된 메뉴 설명의 맛 단서로 제외를 확인한다. 기존 숫자 맛 점수로 순위를 다시 계산하지 않는다. 잘못된 쉼표 금액, 지원하지 않는 한글 금액, 음수 및 잘못된 범위 끝값은 임의로 추측하지 않고 미해석 조건으로 남긴다. 미해석 가격 조건이 남은 추천은 거부한다. 정상 금액 및 명시적 정정은 기존 지원을 유지한다.

기준 커밋을 두 번 추출하고 수정본에 서비스 두 파일만 적용한 무료 비교에서 동일한 45개 메뉴와 설명을 사용했다. 판매 상태는 시험용으로 전부 True이며, 실제 운영 DB의 판매 상태가 아니다. 음성 라우트 비교는 함수 직접 호출이며 HTTP 전송/미들웨어를 검증한 결과가 아니다.

변경 파일: `backend/app/services/recommendation_conditions.py`, `backend/app/services/taste_evidence.py`, `backend/tests/test_recommendation_input_guards.py`.

## 무료 검증

- 백엔드 관련 테스트 42개 통과: 새 입력 회귀 8개, 기존 직접 추천/공식 메뉴 자료/자연어 조건/음성 LLM 연결 검사.
- 프론트 단위 테스트 43개 통과.
- Chrome 브라우저 테스트 10개 통과: 새 방문 기록 회귀 7개, 기존 시작/포장/복수 음성 주문 3개.
- `npm run build` 타입 검사 및 프로덕션 빌드 통과.
- `git diff --check` 통과.

백엔드 재현 명령(프로젝트 루트, 의존성이 설치된 Python 환경):

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path + ';' + (Resolve-Path backend/tests).Path
python -X utf8 -B -m unittest test_recommendation_input_guards test_llm_direct test_menu_research test_speech20.NaturalConditionTests test_voice_llm_integration -q
```

프론트 재현 명령:

```sh
cd frontend
npm ci
npm test
npm run build
npx playwright install chromium
npx playwright test e2e/browser-history.spec.mjs e2e/start-service.spec.mjs
```

이번 로컬 브라우저 검사는 실행 중인 5174 Vite와 설치된 Chrome을 사용했다. 위 기본 명령은 저장소의 Playwright 설정에 따라 별도 5177 서버/Chromium으로 실행한다.

## 한계 및 공유 범위

- 실제 유료 LLM 호출, 마이크/Whisper 전사, 실제 주문 DB 저장 및 서비스 배포 검증은 하지 않았다. 브라우저 테스트의 메뉴·주문·음성 응답은 대체했다.
- 의도적으로 주입한 레몬에이드 응답이 통과하던 서버 검증 문제를 입증한 것이며, 실제 LLM이 그 메뉴를 선택했다거나 추천 정확도가 향상됐다는 측정은 아니다.
- 한국어 부정 표현 처리는 제한적이다. 모든 복합 부정/공동 후행 부정을 이해하지 않는다.
- 설명에 맛 단서가 없다는 사실은 성분 미포함 또는 알레르기 안전성을 보장하지 않는다.
- `일만오천원`을 15000원으로 새롭게 해석하는 기능은 아니다. 지원하지 않는 금액의 오류 처리를 안전하게 변경했다.
- 공용 Dockerfile/compose.yaml, DB 구조, 모델/프롬프트 및 기존 숫자 점수 자료는 변경하지 않았다. 키나 .env, 로컬 Docker 실행 보조 파일도 공유 대상이 아니다.
- 이 브랜치를 공유하는 작업이며 main 병합/배포는 별도 검토 대상이다.
