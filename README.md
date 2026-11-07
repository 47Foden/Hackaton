# Pretuning: 메뉴 속성표 생성

모델 가중치를 학습하는 코드가 아니라, 웹 검색을 활용해 추천용 메뉴 속성 점수를 사전에 만드는 코드입니다.

- `common/menu_data.py`: 메뉴 11개, 종류별 메뉴, 속성과 가격 후보 공통 정의.
- `common/menu_prices.json`: 메뉴별 실제 가격 입력. 지정되지 않은 가격은 null이며 실행 전 입력해야 합니다. 가격 후보 10개를 메뉴 11개에 임의 배정하지 않습니다. 여러 메뉴가 같은 가격을 가져도 됩니다.
- `main.py`: 실행 진입점.
- `pretuning.py`: 검색 기반 평가 5회, 검증, 정규화, 평균 및 CSV 저장.

## 실행

Python 3.12 기준, 프로젝트 루트에서:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt
```

`backend/.env.example`을 `backend/.env`로 복사하고 `OPENAI_API_KEY`를 입력합니다. 기존 파일은 덮어쓰지 않습니다. 환경에 이미 설정된 키를 우선 사용하며 실제 키는 커밋하지 않습니다.

`common/menu_prices.json`의 모든 null을 3000~7500 사이 500원 단위의 실제 가격으로 바꾼 뒤:

```sh
python main.py --model gpt-6luna --output outputs/first-run
python -m unittest discover -s tests -v
```

`gpt-6luna`는 요청된 기본 모델명이며 실제 OpenAI API 제공 여부는 확인되지 않았습니다. 실행 시 모델 접근을 확인하고, 검색·구조화 출력 미지원 시 오류로 중단합니다. 사용 가능한 정확한 모델 ID를 확인한 경우 `--model`로 지정하세요. 임의로 다른 모델로 전환하지 않습니다. 각 평가를 자유 형식 웹 조사 → 구조화된 점수 생성의 두 단계로 수행합니다. 5회 평가에 총 10회 Responses API 요청과 검색 도구 비용이 발생합니다.

## 결과

- `binary.csv`: 행=메뉴, 열=커피/티/에이드/라떼/논커피라떼, 값=0 또는 1. 라떼는 카페라떼·딸기라떼·말차라떼에 표시되는 중복 가능한 속성입니다.
- `continuous.csv`: 행=메뉴, 열=단맛/신맛/쓴맛/가격. 맛은 매 회 0~10 척도로 평가 후 10으로 나누어 0~1로 정규화하고, 정확히 5회 산술평균을 냅니다. 가격은 `(실제 가격-3000)/4500`이며 모델에 추정시키지 않습니다.
- `research_1.json`~`research_5.json`: 검색 출처와 조사 응답 원본. 검색 action.sources와 응답의 url_citation 인용을 모두 확인합니다.
- `run_1.json`~`run_5.json`: 점수 생성 응답 원본. 응답은 검증 전에 저장하므로 실패 원인도 확인할 수 있습니다. 출처가 없거나 메뉴 누락·중복 또는 범위 오류가 있으면 중단합니다.
- `metadata.json`: 모델, 가격 및 계산 기준.

맛 점수는 검색 자료를 참고한 추정치로 레시피·브랜드에 따라 달라집니다. 연속 속성 점수이며 클래스 확률이나 실측값은 아닙니다. 5회 모두 같은 모델·척도를 사용합니다. 실패 시 기존 실행 폴더를 보존하고 최종 CSV를 만들지 않습니다. 다시 실행할 때 새로운 출력 경로를 사용하세요.
