# 음성 주문 옵션 계약·검증 결과

- 검증일: 2026-11-10 (Asia/Seoul)
- 브랜치: `feat/voice-order-option-autoselect`
- 대상: [구현 계획 4번](voice-order-option-autoselect.md), [음성 API 계약](../api-spec.md#72-post-apivoiceinterpret--전사와-주문-단계-해석)
- 결론: 계약 정리 및 자동 검증 완료. 실제 사람이 마이크로 발화하는 현장 확인은 미수행.

## 실행 결과

| 검증 | 결과 | 검증 범위 |
| --- | --- | --- |
| 프론트 `npm run build` | 통과 | TypeScript 및 Vite 프로덕션 빌드 |
| 프론트 `npm test` | 41개 통과 | 응답 검증, 필드 병합, 옵션 검증, 미선택 단계 전이, 기존 주문 회귀 |
| 백엔드 `unittest discover -s tests` | 84개 통과 | 음성 해석·추천 계약, 오디오, 주문/메뉴 API, DB 및 기존 음성 아카이브 테스트 |
| Playwright 전체 | 33개 통과 | 가상 마이크, 음성·터치 주문, 추천, 화면/음성 안내 생략, 실패·재시도, 메뉴 화면 |
| 실제 Whisper + 실제 음성 해석 API | 통과 | 기존 합성 음성 샘플 결합 → WebM/Opus → 실제 전사 → COLD/TAKEOUT 동시 반환 |
| 실제 사람의 마이크 발화 | 미수행 | 아래 현장 확인 절차로 수행 필요 |

첫 백엔드 전체 실행은 음성 아카이브 파일이 테스트 컨테이너에 연결되지 않아 2개가 오류였다. 저장소의 `speech17_20261107081708001.zip`을 읽기 전용으로 마운트한 뒤 전체 84개가 통과했다. 실행 도중 자동 승인 검토 서비스 사용량 한도로 브라우저 실행이 한 번 중단됐으나 사용자 재개 요청 후 정상 실행했다. 두 문제 모두 최종 자동 검증의 미해결 실패는 아니다.

## 보완 사항

- API 명세의 오래된 후보 수 제한(1~4개)을 실제 카탈로그 메뉴 수 제한으로 수정했다.
- `review`, `confirm`, `restart_recommendation` 계약과 명시적 음성 최종 확인을 문서화했다.
- 미언급, `pending`, 명시적 빈 옵션, 충돌, 지원하지 않는 옵션의 응답 및 화면 처리 예시를 추가했다.
- 계획서의 “네, 샷도 추가해 주세요”를 회귀 테스트에 추가하면서 `샷도 추가`를 인식하지 못하는 문제를 발견했다. 샷·시럽의 `도` 조사 포함 동의어를 보완했고 테스트가 통과했다.
- 샷만 지정한 주문 및 샷+바닐라 시럽 주문을 실제 주문 API/격리 DB에서 검증했다. 선택 ID, 추가 금액(샷 600원·바닐라 시럽 700원), 현재 DB 메뉴 가격을 합산한 총액, DB 옵션 스냅샷 및 동일 요청 재전송 결과를 확인했다.
- 브라우저에서는 카탈로그 기반 mock 주문 서버로 확인 화면·요청·완료 화면의 선택 내역과 금액이 일치하는지 검증했다. 이는 실제 DB 통합 테스트와 구분된다.

## 인수 기준과 근거

| 조건 | 검증 근거 |
| --- | --- |
| 아이스+포장, 매장만 지정, 옵션 미언급 | 백엔드 계약 예제 테스트 및 reducer 선택 여부 8가지 조합 테스트 |
| “시원한 음료 추천”의 온도 보존, 모델이 제시한 온도와 구분 | 음성 API 추천 테스트, 브라우저 추천→터치 선택→음성 확인 테스트 |
| “아이스로 포장” 복합 옵션 | API 계약 예제 및 실제 Whisper 합성 음성 검증 |
| 샷 추가 후 온도 미지정 | `pending` 계약 테스트, 온도 선택 후 의도 재검증 테스트 |
| 온도·샷·포장을 모두 지정 | reducer 단일 전이, 화면 DOM 삽입/음성 안내가 없는지 브라우저 감시 |
| 샷+시럽, 샷만 지정 | 실제 주문 API/DB 및 브라우저의 가격·선택 내역 검사. 미언급 그룹의 추가 선택 없음 확인 |
| 명시적 “추가 옵션 없이” | API 계약 예제, 빈 resolved와 pending 구분, 브라우저 전체 옵션 화면 생략 |
| 커스터마이징 단계의 음성 입력 | 단계별 요청 맥락 및 `set_options` API 테스트, 브라우저 마이크 사용 가능 확인 |
| “샷 추가하고 시럽도” | 유효한 샷을 유지한 `needs_clarification`, 선택된 버튼 및 수동 확인 후 이동 검사 |
| 정정·부정·충돌·중복·개수 초과 | 백엔드 옵션 해석 테스트, 프론트 병합 및 reducer 테스트 |
| 메뉴/온도에 없는 옵션 | 카탈로그별 재검증, 단일 온도라도 반대 온도로 대체하지 않는 테스트 |
| 재추천·새 주문·늦은 응답 | 브라우저 재추천 초기화, 완료 후 새 음성 주문의 온도 화면, 지연 응답 무시 테스트 |
| 최종 확인 전 주문 전송 금지 | 브라우저 주문 호출 횟수 검사 및 기존 명시적 확인 회귀 테스트 |

주요 테스트 파일:

- [백엔드 음성 옵션 및 응답 계약](../../backend/tests/test_voice_options.py)
- [실제 주문 API·DB 통합](../../backend/tests/test_orders_api.py)
- [프론트 세션·옵션 검증](../../frontend/tests/voice-options.test.mjs)
- [미선택 단계 계산](../../frontend/tests/order-next-stage.test.mjs)
- [브라우저 음성 옵션 검증](../../frontend/e2e/voice-options.spec.mjs)

## 실제 전사 경로 확인

기존 `recordings/whisper-benchmark/cold.wav`, `takeout.wav` 합성 음성을 FFmpeg로 결합하여 WebM/Opus로 인코딩했다. 실행 중인 개발 API에 `stage=temperature`, `selected_menu_id=cafe_latte`와 함께 전달했다. 해당 단계는 LLM 추천을 호출하지 않고, 주문도 생성하지 않는다.

실제 응답:

```json
{
  "transcript": "차갑게 해주세요. 포장해주세요.",
  "action": { "type": "set_temperature", "temperature": "COLD" },
  "recognized_options": {
    "temperature": "COLD",
    "service_type": "TAKEOUT",
    "unresolved_fields": []
  }
}
```

이 결과는 실제 Whisper와 API 연결 검증이며 사람 발화·주변 소음·브라우저 실제 마이크 품질 또는 실제 LLM 추천 품질 검증을 대체하지 않는다. 새 한국어 SAPI 샘플 생성은 로컬 음성 엔진 접근 오류로 실행하지 못해 기존 합성 음성 파일을 사용했다.

## 재실행 명령

저장소 루트에서 PowerShell로 실행한다. DB 테스트는 임시 스키마를 만들고 테스트 후 삭제하며 기존 주문 스키마를 사용하지 않는다.

```powershell
$testRoot = (Get-Location).Path.Replace('\', '/')
docker compose run --rm --no-deps `
  -v "${testRoot}/backend/tests:/app/tests:ro" `
  -v "${testRoot}/speech17_20261107081708001.zip:/speech17_20261107081708001.zip:ro" `
  backend python -m unittest discover -s tests

Set-Location frontend
npm run build
npm test
npx playwright test
```

검증 환경에서는 로컬 소켓 접근 제한 때문에 별도 터미널에서 `npm run dev -- --host 127.0.0.1 --port 5181`을 실행하고 아래 설정으로 브라우저 테스트를 실행했다. 테스트용 서버는 검증 후 종료했다.

```powershell
$env:PLAYWRIGHT_EXTERNAL_SERVER = '1'
$env:PLAYWRIGHT_BASE_URL = 'http://127.0.0.1:5181'
npx playwright test
```

## 남은 실제 마이크 확인

1. 개발 키오스크에서 음성 주문을 열고 실제 마이크로 “시원한 음료 포장해 주세요”를 말한다.
2. 전사 문장과 추천을 확인한 후 메뉴를 선택·확인한다. 온도·매장/포장 화면이 생략되고 커스터마이징 미언급 시에는 해당 화면이 표시돼야 한다.
3. 새 주문에서 “아이스 카페라떼 샷 추가하고 포장해 주세요”를 말한다. 메뉴 확인 후 바로 최종 확인으로 이동하고 COLD·포장·샷 추가·추가 금액이 표시돼야 한다.
4. “샷 추가하고 시럽도”처럼 모호한 발화에서는 샷 선택을 유지하고 추가 확인 화면을 표시하는지 확인한다.
5. 전사 오류가 있을 때 임의 주문이 전송되지 않는지 확인한다. 실제 주문 저장까지 시험하려면 개발 DB임을 확인하고 최종 확정을 명시적으로 수행한다.

실제 사람의 마이크 발화 결과를 아직 받지 않았으므로 이 항목을 완료로 표시하지 않는다.
