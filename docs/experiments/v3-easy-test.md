# v3 쉬운 발화 5개 확인

목적은 확인된 메뉴 설명·가격·온도 조건으로 후보 하나를 제대로 선택하는지 사람이 읽고 판단하는 것이다. 재질문 이후 대화나 추상적인 뒷맛 해석은 이번 범위에 포함하지 않는다.

발화는 `common/experiments/llm_direct/v3_easy_cases.json`에 있다. 예산과 커피 제외, 따뜻한 커피, 레몬 산미·탄산, 딸기·우유, 청포도·탄산의 5개 사례다. 복수 메뉴가 조건을 만족하면 모두 허용한다. 예상 메뉴와 필요한 근거는 별도 평가용이며 LLM 요청에 전송하지 않는다. 기존 추천에는 기존 CSV/규칙, v3에는 확인된 설명·성분 자료가 추가된다는 차이를 기록한다.

저장소 루트 PowerShell, Python 3.11 이상에서 무료 확인:

```powershell
$env:PYTHONPATH = (Resolve-Path backend).Path
python -B -m app.experiments.run_easy_v3 --v1-report docs/experiments/2026-11-09-first-live/results.json --output-dir work/v3-easy-mock
```

`results.json`과 `report.ko.md`를 생성한다. mock 보고서의 성능·시간·토큰·비용은 미측정이다. 이미 존재하는 출력 폴더는 실행 전 차단한다.

실제 호출은 키 소유자가 직접 실행한다. 위 명령에 `--mode live --allow-paid-api --model <모델> --env-file backend/.env`를 추가하고 별도 출력 폴더를 사용한다. .env를 콘솔에 출력하지 않는다. 단가를 알고 있으면 `--rates INPUT CACHED_INPUT OUTPUT`에 백만 토큰당 USD 단가를 명시한다. 단가가 없거나 usage가 없으면 비용은 미상이다. dotenv 사용을 위해 python-dotenv가 필요하다.

실행은 발화별 한 번, 최대 5회, 자동 재시도 없음이다. 시도 시작과 응답은 `api-attempts.json`에 기록한다. 중단되면 해당 기록을 확인하고 같은 실험을 무심코 다시 실행하지 않는다. 5회 제한은 강제 결제 금액 상한이 아니다. 프롬프트·인증 헤더·키는 이 호출 기록에 저장하지 않는다.

보고서에는 발화별 후보·확인된 근거·질문/오류·거부된 원래 응답·기존 방식 결과·별도 사실 점검·토큰·시간·비용과 단점을 담는다. 기대 메뉴·조건·근거 충족은 제한된 사례 판정이며 일반적인 추천 정확도나 사용자 만족도가 아니다. 각 1회로 반복 일관성은 알 수 없다. 저장 메뉴 스냅샷과 조사 자료를 사용하므로 현재 매장 상태를 보장하지 않는다.

운영 웹·음성·기존 추천·팀 Docker 설정은 변경하지 않는다. 실제 결과를 검토하기 전에는 v2보다 개선됐다고 결론 내리지 않는다.
