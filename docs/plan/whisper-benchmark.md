# Whisper 실행 장비와 한국어 전사 벤치마크

- 측정일 2026-11-07 · 대상 브랜치 `feat/voice-recommendation-integration`
- 기준 [5단계 실제 음성·추천 통합 계획](voice-recommendation-integration.md)

## 실행 장비와 입력 장치

| 항목 | 선택 및 확인 결과 |
| --- | --- |
| 키오스크 브라우저 | Google Chrome `156.0.8078.81` |
| 마이크 | Windows에 연결된 내장 마이크 배열, Intel Smart Sound Technology for Digital Microphones |
| 실행 위치 | 같은 PC의 Windows 호스트에 설치한 벤치마크용 Python 가상 환경 |
| OS | Windows 11 Home, 빌드 `26300` |
| CPU | Intel Core Ultra 7 155H, 16코어·22논리 프로세서 |
| GPU | Intel Arc Graphics 내장 GPU, 드라이버 `32.0.101.8132`. 이번 측정은 CPU에서 실행 |
| 메모리 | Windows 인식 총 31.61 GiB, 장비 확인 시 가용 약 9.83 GiB |
| 모델 | `openai/whisper-large-v3-turbo`, 리비전 `41f01f3fe87f28c78e2fbf8b568835947dd65ed9` |
| 실행 설정 | Python 3.12.10, PyTorch `2.9.1+cpu`, Transformers `4.57.6`, Accelerate `1.12.0`. CPU FP32, PyTorch 연산 스레드 8개, 한국어 전사, greedy 디코딩 |

공식 리비전의 `model.safetensors`는 1,617,824,864바이트다. 다운로드 파일의 SHA-256 `542566a422ae4f3fd23f1ba11add198fca01bbf82e66e6a2857b3f608b1eb9d1`을 Hugging Face 응답의 체크섬과 대조했다. 전사는 로컬 파일과 로컬 모델로 실행한다. [Hugging Face 모델 카드](https://huggingface.co/openai/whisper-large-v3-turbo)

## 샘플과 측정 기준

- Windows `Microsoft Heami Desktop - Korean`으로 메뉴명 5개와 옵션 4개를 합성했다. 정답 문구는 [샘플 목록](../../backend/scripts/voice/korean_samples.json)에 있다. 파일은 16 kHz 모노 PCM16 WAV이며 발화별 1.90~2.62초다.
- 문장 완전 일치, 메뉴명·옵션 핵심어 포함 여부, 문자 오류율(CER)을 분리한다. 공백·문장부호는 비교에서 제외한다. CER은 전체 문자 편집 거리 합계를 전체 정답 문자 수로 나눈 값이다.
- 첫 호출은 모델을 로드한 직후 아이스 아메리카노 샘플로 측정한다. 재호출은 같은 프로세스와 모델에서 9개 샘플을 각각 두 번 전사한다. 정확도 집계에는 샘플별 첫 재호출 결과를 사용한다.
- 전사 시간은 이미 읽어 둔 PCM의 특징 추출부터 전사 문자열 반환까지다. 모델 다운로드, 마이크 캡처, 업로드, 서버 변환은 별도로 측정한다.
- 저장소의 MP3 20개에는 정답 전사 파일이 없어 정확도 집계에서 제외했다. 이번 정확도는 합성 입력 기준이며, 실제 마이크 발화와 브라우저 녹음 형식 검증은 별도 인수 항목이다.

## 실측 결과

| 지표 | 값 |
| --- | --- |
| 최초 프로세스의 Python 패키지 import | 61.57초 |
| 로컬 모델 및 프로세서 로딩 | 1.94초 |
| 모델 로드 직후 첫 전사 | 14.96초 |
| 첫 결과까지 위 세 구간 합계 | 78.48초 |
| 모델 재사용 전사 18회 | 중앙값 12.30초, 범위 5.58~14.44초 |
| 전사 직전 시스템 가용 메모리 | 8.97 GiB |
| 측정 종료 시 Python 프로세스 RSS | 3.55 GiB |
| 정규화한 전체 문장 일치 | 9/9, 메뉴 5/5 및 옵션 4/4 |
| 핵심어 일치 / 문자 오류율 | 9/9 / 0% |

최초 import는 실험용 가상 환경을 처음 구성한 실행에서 한 번 관측했다. 가중치 다운로드는 위 구간에 포함되지 않는다. 종료 시 RSS는 최대 사용량을 뜻하지 않는다.

| 발화 핵심어 | 정규화한 문장 일치 | 재호출 2회 중앙값 |
| --- | --- | ---: |
| 아이스 아메리카노 | 일치 | 9.24초 |
| 카페라떼 | 일치 | 14.05초 |
| 레몬티 | 일치 | 8.48초 |
| 레몬차 | 일치 | 11.82초 |
| 녹차라떼 | 일치 | 12.60초 |
| 따뜻하게 | 일치 | 12.65초 |
| 차갑게 | 일치 | 12.35초 |
| 매장에서 | 일치 | 9.35초 |
| 포장 | 일치 | 5.64초 |

### Chrome 녹음 검사·변환 지연

Docker의 FFprobe·FFmpeg 7.1.5로 각 샘플을 7회 검사하고 16 kHz 모노 PCM16으로 변환했다. 임시 파일 쓰기와 두 도구의 실행 시간을 포함했다.

| 입력 | 길이 | 업로드 크기 | 중앙값 | 최대 |
| --- | ---: | ---: | ---: | ---: |
| Chrome WebM/Opus 녹음 | 2.76초 | 37,972바이트 | 105.5ms | 107.5ms |
| 같은 오디오를 반복해 만든 WebM/Opus | 30.00초 | 317,804바이트 | 171.9ms | 176.1ms |

## 재현 방법

저장소 루트에서 PowerShell로 실행한다. 실험용 패키지는 `backend/scripts/voice/.venv`에 설치한다. 한국어 SAPI 음성이 설치된 Windows가 샘플 생성에 필요하다. [PyTorch CPU 설치 기준](https://pytorch.org/get-started/previous-versions/)

```powershell
python -m venv backend/scripts/voice/.venv
$benchPython = './backend/scripts/voice/.venv/Scripts/python.exe'
& $benchPython -m pip install --index-url https://download.pytorch.org/whl/cpu 'torch==2.9.1'
& $benchPython -m pip install 'transformers==4.57.6' 'accelerate==1.12.0'
& ./backend/scripts/voice/.venv/Scripts/hf.exe download openai/whisper-large-v3-turbo --revision 41f01f3fe87f28c78e2fbf8b568835947dd65ed9 --local-dir models/whisper-large-v3-turbo --include '*.json' merges.txt model.safetensors
& ./backend/scripts/voice/generate_korean_samples.ps1
& $benchPython backend/scripts/voice/benchmark_whisper.py --threads 8 --warm-repeats 2
```

재현 스크립트와 정답 목록은 `backend/scripts/voice/`에 둔다. 모델 가중치, 생성된 WAV 및 실행별 `report.json`은 각각 Git에서 제외된 `models/`와 `recordings/whisper-benchmark/`에 둔다.
