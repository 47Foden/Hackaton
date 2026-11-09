# 45종 추천 점수표

기존 11종 실험 CSV와 전용 메뉴 매핑은 제거했다. 주문 카탈로그 `common/order_catalog.json`의 45종을 사용한다.

- `binary.csv`: 45종 × 12개 분류의 실제 카탈로그 기반 이진 행렬.
- `continuous.csv`: 사용자 PC에서 완료한 45종 맛 평가 결과를 넣을 위치. 현재 저장소에는 없다.

새 맛 평가 결과를 전달하기 전에는 추천 요청 시 점수표 미준비 안내를 표시한다. 기존 11종 점수로 대체하지 않는다.
메뉴 이름 선택과 일반 터치 주문은 가능하다.

저장소 루트 PowerShell에서 생성한 45종 결과를 적용한다.

```powershell
Copy-Item .\outputs\taste-45-run1\binary.csv .\common\recommendation\binary.csv
```

```powershell
Copy-Item .\outputs\taste-45-run1\continuous.csv .\common\recommendation\continuous.csv
```

두 CSV에는 동일한 45종 이름이 정확히 한 번씩 있어야 한다.
`continuous.csv` 열은 `메뉴,단맛,신맛,쓴맛`, 값은 0~1이다.
이진 분류 열은 `outputs/catalogue-45/binary.csv`와 동일해야 한다.
가격은 DB에서 읽으며 정규화하지 않는다. 디카페인은 상품 분류로 처리하고 카페인 함량은 추정하지 않는다.
