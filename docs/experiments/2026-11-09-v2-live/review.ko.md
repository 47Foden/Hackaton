# v2 첫 실제 실험 검토

**실행은 완료됐지만 추천 품질 개선이 입증된 결과는 아닙니다. 추가 API 호출·키 파일 접근·commit·push 없이 결과만 검토했습니다.**

- 새 발화 10개 × 1회. 서버 검증 통과 2건: 추천 1건, 모순 조건 확인 질문 1건. 거부 8건.
- 총 비용 추정 USD 0.11519400, 평균 지연 2.656초.
- 입력 총 141166토큰, 출력 총 2071토큰. 요청당 입력 약 1.4만 토큰으로 자료가 길어졌습니다.
- 각 발화 한 번이므로 반복 일관성은 미측정입니다. v1과 데이터셋/입력 자료가 달라 통과 건수만으로 우열을 비교하지 않습니다.

| 발화 ID | 서버 결과 | 검토 |
|---|---|---|
| new_budget_ceiling | recommend | 추천 통과: 3000원 이하 COLD 후보 선택. |
| new_coffee_refusal | TAG_SCOPE_MISMATCH | 태그 ID를 refreshing/tart처럼 짧게 반환. 일부 후보의 refreshing 근거 부족도 별도 확인 필요. |
| new_milk_refusal | INELIGIBLE_OPTION | milk=false 확인 자료가 없는데 과일 음료를 추천. 자료 부족/질문으로 처리했어야 할 문제. |
| new_do_not_exclude_coffee | CAFFEINE_EVIDENCE_REQUIRED | 커피 후보 선택은 예산 안이지만 fit=caffeine을 선택하고 카페인 근거를 인용하지 않음. fit 명칭의 의미 혼동 가능. |
| new_explicit_zero_caffeine | TAG_SCOPE_MISMATCH | 0mg COLD 후보 자체는 확인된 자료와 맞지만 태그 ID의 tag: 접두사를 빠뜨림. |
| new_lingering_sweetness | TAG_SCOPE_MISMATCH | 뒷맛 미확인에도 질문 없이 추천. 태그 ID 형식도 틀림. 형식을 고쳐도 적합성은 별도 검토 필요. |
| new_astringent_mouthfeel | TAG_SCOPE_MISMATCH | 떫음 미확인에도 추천. 태그 ID 형식과 일부 unsupported refreshing 태그 문제도 있음. |
| new_unknown_menu | MILK_EVIDENCE_REQUIRED | 없는 바닐라 오트라떼 대신 카페라떼를 선택. fit=milk는 우유 포함 느낌으로 해석했지만 서버에서는 우유 미포함 근거를 요구해 거부. |
| new_conflicting_budget | clarify | 모순을 인식하고 질문해 통과. 다만 맛/제외 조건까지 덧붙여 질문이 넓어짐. |
| new_embedded_instruction | MILK_EVIDENCE_REQUIRED | 등록된 메뉴 ID와 예산은 지켰음. fit=milk/caffeine 의미와 근거 요건 혼동으로 거부. 이것만으로 일반적인 주입 방어 성공을 보장하지 않음. |

## 실패 유형

- TAG_SCOPE_MISMATCH 4건: 모델은 refreshing 또는 lemonade:COLD:refreshing을 썼으나 서버는 tag:lemonade:COLD:refreshing을 요구했습니다. 길고 반복적인 식별자 형식의 설계 부담입니다. 일부는 해당 메뉴에 지원되지 않는 태그도 있어 접두사만 고치면 모두 성공한다고 말할 수 없습니다.
- CAFFEINE_EVIDENCE_REQUIRED 1건, MILK_EVIDENCE_REQUIRED 2건: fit=caffeine/milk를 모델은 커피/우유 계열로 이해한 듯하지만 서버는 카페인 기준/우유 미포함 근거로 정의했습니다. 응답 필드의 의미가 덜 명확했던 설계 문제를 포함합니다.
- INELIGIBLE_OPTION 1건: 우유 미포함이 확인되지 않았는데 후보를 반환했습니다. 형식 문제가 아닌 조건/자료 처리 문제입니다.

## 다음 수정 제안

1. 메뉴 ID와 온도를 이미 선택했으므로 태그는 짧은 enum 이름으로 반환하게 하고 서버가 그 메뉴/온도 안에서만 연결합니다. 잘못된 태그나 미확인 태그를 허용하거나 기존 실패를 성공으로 다시 쓰지는 않습니다.
2. milk/caffeine처럼 중의적인 fit 분류를 없애거나 의미를 분리합니다. 가격/우유/카페인 조건의 검증은 실제 사실에서 수행하고 분류 단어에 불필요한 요건을 매달지 않습니다.
3. 추천에 충족시킨 요구와 아직 해결하지 못한 요구를 구분하도록 응답을 단순화합니다. 우유 미확인·뒷맛 미확인·없는 메뉴는 질문/자료 부족으로 이어지는지 다시 시험합니다.
4. 최초 추천과 서버 거부 결과를 그대로 보존하고, 수정 후에는 같은 10개를 회귀 검증합니다. 최종 개선 판단은 별도의 새 문장과 독립된 사람 평가가 필요합니다.

## 코드 테스트와 실제 추천 평가의 차이

앞서 76개 테스트 통과는 요청/검증/오류/보존 로직이 정의대로 동작했다는 의미입니다. 실제 모델이 그 형식과 의미를 안정적으로 따르거나 좋은 추천을 한다는 증거는 아닙니다. 이번 실험은 그 차이를 드러냈습니다.

현재는 배포할 품질이라고 판단하지 않습니다. 입력과 응답 구조를 단순화하고 실제 실패에 맞춘 회귀 검증을 먼저 하는 것이 적절합니다.