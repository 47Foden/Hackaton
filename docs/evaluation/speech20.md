# 실제 음성 20개를 활용한 추천 해석 개선

## 데이터 출처와 전사

원본은 저장소의 `speech17_20261107081708001.zip`이다. ZIP의 MP3 20개를 실제로 읽고 SHA-256과 길이를 기록했다. 사용자가 파일명 번호와 앞서 제공한 엑셀 번호가 다르다고 확인했으므로, 번호로 전사나 정답을 연결하지 않았다.

임시 CPU 환경에서 faster-whisper base와 small을 각각 한국어·INT8·beam 5로 실행했다. 두 모델이 `프라페`·`디카페인`을 다르게 인식한 파일은 small에 카페 어휘 힌트를 주어 추가 전사했다. 서버의 운영 Whisper 모델이나 설정은 변경하지 않았다. 전사 원문·후보·수정 선택과 해석은 `common/evaluation/speech20.json` 및 `speech20-review.csv`에 보존한다.

이 전사와 조건 라벨은 **사람이 검수하지 않은 초안**이다. 어휘 힌트가 특정 단어를 유도할 수 있으므로 정답으로 확정하지 않았다. 검수자는 CSV에서 원음을 들어 확인하고, 평가 JSON의 `reference_text`, `expected_conditions`, 검수 상태를 함께 갱신해야 한다.

## 운영 코드에 반영한 내용

- 12개 발화의 조건 해석 예시를 `common/recommendation_examples.json`으로 분리해 실제 LLM 요청에 넣는다. 구체적인 정답 메뉴 ID나 맛 점수표는 넣지 않는다.
- 8개는 프롬프트에 넣지 않는다. 개발자가 20개를 모두 살펴봤으므로 이 8개도 독립적인 외부 성능 검증 세트는 아니다.
- 오천 원/5천 원/5,000원, 가격 범위, 원대, 미만·이하·안으로, 대략적인 가격 선호, 제외 표현과 온도를 구분한다.
- `두 개 추천`은 추천 후보 최대 2개로 처리한다. 출력 스키마에 상한을 주고 서버에서도 적용한다. 개수가 없으면 적합한 모든 후보를 유지한다. 적합도 순서는 LLM이 정하고, 명시적인 가격순/근접 가격 요청만 숫자 가격으로 정렬한다.
- 현재 메뉴 분류로 커피·디카페인·프라페·스무디·주스·티 등 포함·제외 조건을 검증한다. 커피 제외 시 디카페인 커피도 제외하지만 무카페인으로 간주하지 않는다.
- 실제 온도별 옵션 목록을 LLM에 제공한다. 두유 변경 요청은 실제 해당 옵션이 있어야 가능하며, 없는 옵션을 생성하지 않는다.
- `두 잔 합쳐서 8,000원`은 한 잔 8,000원이 아니다. 총액·수량을 따로 보존한다. 현재 주문 API가 단일 메뉴·한 잔만 지원하므로 조합 주문이 가능한 것처럼 추천하지 않는다.
- 되묻는 질문·대화 기록 안내는 다시 넣지 않았다. 자료 부족·불명확한 지칭은 임의의 메뉴로 대체하지 않는다.

이는 **few-shot 예시와 검증 코드 개선**이다. 모델 가중치 학습·파인튜닝을 수행한 것은 아니다.

## 검증 결과의 범위

오프라인 진단에서 20개 초안의 조건 체크가 모두 통과했다. 이전 guard가 새 필드를 포함한 동일 체크를 만족한 것은 3개였고, 변경 후에는 20개다. 이는 새 기능을 포함한 **조건 체크 커버리지**이며 LLM 추천 정확도 15%→100%라는 의미가 아니다. 변경 전 실제 LLM 응답은 수집하지 않았다.

이 환경에는 OpenAI API 키가 없으므로 유료 LLM의 전후 추천 품질·응답 시간·비용은 측정하지 않았다. `speech20-offline-summary.json`에도 추천 품질 미측정과 사람 검수 미완료를 명시한다. 메뉴 적합도 평가는 사람이 결과를 검토해 별도 라벨링해야 한다.

## 로컬 Docker에서 다시 평가

최신 코드를 받고 개인용 `backend/.env`의 OpenAI 키·전사 주소를 반영한 뒤 백엔드를 재생성한다. DB 메뉴와 RunPod Whisper·SSH 터널은 기존대로 실행한다.

API 호출 없이 조건 체크만:

```powershell
docker compose exec backend python -m app.evaluation.speech20 --output /tmp/speech20-offline
```

검토용 전사 텍스트로 LLM 평가(최대 20개 추천 호출, 과금):

```powershell
docker compose exec backend python -m app.evaluation.speech20 --mode live-text --output /tmp/speech20-text
```

원본 음성→현재 Whisper→LLM 전체 평가(20개 전사 요청 및 최대 20개 추천 호출, 과금):

```powershell
docker compose cp .\speech17_20261107081708001.zip backend:/tmp/speech20.zip
```

```powershell
docker compose exec backend python -m app.evaluation.speech20 --mode live-audio --archive /tmp/speech20.zip --output /tmp/speech20-audio
```

결과를 내 PC로 복사:

```powershell
docker compose cp backend:/tmp/speech20-audio .\speech20-audio-results
```

결과는 `results.json`과 Excel/VS Code에서 열 수 있는 `results.csv`다. 실제 전사·조건 누락·추천 ID·토큰 사용량·전체 소요 시간이 기록된다. 같은 출력 디렉터리는 덮어쓰지 않으므로 재실행할 때 새 이름을 사용한다. 오류는 자동 재시도하지 않는다. 실행 중 다른 사용자가 같은 Whisper 워커를 사용하면 busy가 발생할 수 있으므로 평가할 때는 순서대로 사용한다.

새 발화로 일반화 성능을 확인하려면 20개와 별개인 추가 발화를 모으고, 사람 검수한 전사·조건·적합 메뉴를 붙여 프롬프트에 노출하지 않은 상태로 평가한다.
