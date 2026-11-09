# 첫 LLM 직접 추천 실험

실행 방식: live / 모델: gpt-5.4-mini-2026-03-17

연결 확인 1회 후 다섯 발화 각 1회. 자동 재시도 없음. 키는 보고서에 기록하지 않음.
반복 일관성은 미측정이며 실제 적합성/근거 정확성은 사람 검토가 필요함.

## connection_check

3000원 이하 차가운 음료 추천해 주세요.

**기존 추천**: ok / 2.409 ms

```json
{
  "menu_ids": [
    "espresso",
    "peach_iced_tea",
    "iced_americano",
    "cafe_latte"
  ]
}
```

메뉴 이름: 에스프레소, 복숭아 아이스티, 아이스아메리카노, 카페라떼

**LLM 직접 추천**: error / 4666.14 ms

검증/실행 오류: CONSTRAINT_VIOLATION

```json
{
  "status": "recommend",
  "recommendations": [
    {
      "menu_id": "iced_americano",
      "temperature": "COLD",
      "reason": "3,000원 이하의 차가운 음료입니다."
    },
    {
      "menu_id": "peach_iced_tea",
      "temperature": "COLD",
      "reason": "3,000원 이하이며 COLD로 제공됩니다."
    },
    {
      "menu_id": "lemon_tea",
      "temperature": "COLD",
      "reason": "차가운 제공이 가능하고 3,000원 초과가 아닙니다."
    },
    {
      "menu_id": "citron_tea",
      "temperature": "COLD",
      "reason": "차가운 제공이 가능하고 3,000원 초과가 아닙니다."
    }
  ],
  "questions": [],
  "missing_information": []
}
```

메뉴 이름: 아이스아메리카노, 복숭아 아이스티, 레몬차, 유자차

usage: {"input_tokens": 4341, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0}, "output_tokens": 155, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 4496}
비용 추정(USD): 0.00395325

## budget_no_coffee

커피는 말고, 삼천 원 한 장으로 살 수 있는 거 있어요?

**기존 추천**: error / 0.952 ms

검증/실행 오류: EXISTING_INPUT_OR_DATA_ERROR

**LLM 직접 추천**: error / 3171.171 ms

검증/실행 오류: CONSTRAINT_VIOLATION

```json
{
  "status": "recommend",
  "recommendations": [
    {
      "menu_id": "lemon_tea_alias",
      "temperature": "HOT",
      "reason": "커피가 아니고 3,300원으로 예산 안에 듭니다."
    },
    {
      "menu_id": "lemon_tea_alias",
      "temperature": "COLD",
      "reason": "커피가 아니고 3,300원으로 예산 안에 듭니다."
    },
    {
      "menu_id": "lemon_tea",
      "temperature": "HOT",
      "reason": "커피가 아니고 3,300원으로 예산 안에 듭니다."
    },
    {
      "menu_id": "lemon_tea",
      "temperature": "COLD",
      "reason": "커피가 아니고 3,300원으로 예산 안에 듭니다."
    }
  ],
  "questions": [],
  "missing_information": []
}
```

메뉴 이름: 레몬티, 레몬티, 레몬차, 레몬차

usage: {"input_tokens": 4347, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0}, "output_tokens": 167, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 4514}
비용 추정(USD): 0.00401175

## clean_finish

입안이 텁텁한데 좀 깔끔하게 마실 만한 거 주세요.

**기존 추천**: error / 0.328 ms

검증/실행 오류: EXISTING_INPUT_OR_DATA_ERROR

**LLM 직접 추천**: error / 4228.861 ms

검증/실행 오류: INVALID_MENU_ID

```json
{
  "status": "recommend",
  "recommendations": [
    {
      "menu_id": "lemon_tea",
      "temperature": "HOT",
      "reason": "레몬의 산미와 향을 강조한 과일 차라서 입안을 깔끔하게 마시기 좋습니다."
    },
    {
      "menu_id": "lemon_tea",
      "temperature": "COLD",
      "reason": "레몬의 산미와 향을 강조한 과일 차라서 시원하게 깔끔한 느낌으로 마시기 좋습니다."
    },
    {
      "menu_id": "lemonade",
      "temperature": "COLD",
      "reason": "레몬의 산미와 탄산의 청량감이 있는 음료로, 텁텁함을 덜고 싶을 때 맞습니다."
    },
    {
      "menu_id": "green_grape_ade",
      "temperature": "COLD",
      "reason": "달콤한 청포도 풍미와 탄산을 조합한 에이드라서 가볍고 상큼하게 마시기 좋습니다."
    }
  ],
  "questions": [],
  "missing_information": []
}
```

메뉴 이름: 레몬차, 레몬차, 레몬에이드, 청포도에이드

usage: {"input_tokens": 4349, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0}, "output_tokens": 213, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 4562}
비용 추정(USD): 0.00422025

## sweet_not_sticky

달달한 건 좋은데, 먹고 나서 입이 끈적할 정도는 싫어요.

**기존 추천**: ok / 2.23 ms

```json
{
  "menu_ids": [
    "strawberry_latte",
    "citron_tea",
    "green_grape_ade",
    "lemonade"
  ]
}
```

메뉴 이름: 딸기라떼, 유자차, 청포도에이드, 레몬에이드

**LLM 직접 추천**: ok / 1999.246 ms

```json
{
  "status": "recommend",
  "recommendations": [
    {
      "menu_id": "lemon_tea",
      "temperature": "HOT",
      "reason": "공식 설명상 과일 차이고, 단맛과 산미를 함께 언급합니다. 끈적함에 대한 정보는 없고 HOT/COLD 모두 가능합니다."
    },
    {
      "menu_id": "citron_tea",
      "temperature": "HOT",
      "reason": "공식 설명상 달콤하고 상큼한 과일 차입니다. 판매 중이고 HOT/COLD 모두 가능합니다."
    },
    {
      "menu_id": "lemonade",
      "temperature": "COLD",
      "reason": "공식 설명상 레몬의 산미와 탄산의 청량감을 특징으로 합니다. COLD만 가능하고 카페인 표기는 0.0입니다."
    },
    {
      "menu_id": "peach_iced_tea",
      "temperature": "COLD",
      "reason": "공식 설명상 홍차에 복숭아의 단맛과 향을 더한 차가운 음료입니다. COLD만 가능하고 판매 중입니다."
    }
  ],
  "questions": [],
  "missing_information": []
}
```

메뉴 이름: 레몬차, 유자차, 레몬에이드, 복숭아 아이스티

usage: {"input_tokens": 4351, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0}, "output_tokens": 222, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 4573}
비용 추정(USD): 0.00426225

## no_milk

우유 들어간 건 빼주세요. 대신 시큼한 건 괜찮아요.

**기존 추천**: error / 0.05 ms

검증/실행 오류: EXISTING_INPUT_OR_DATA_ERROR

**LLM 직접 추천**: error / 2333.588 ms

검증/실행 오류: UNVERIFIED_EXCLUSION

```json
{
  "status": "recommend",
  "recommendations": [
    {
      "menu_id": "lemon_tea",
      "temperature": "HOT",
      "reason": "우유 포함 확인이 없어 제외 조건에 맞을 가능성이 있고, 공식 설명상 레몬의 산미와 향이 강조된 과일 차입니다."
    },
    {
      "menu_id": "lemon_tea_alias",
      "temperature": "COLD",
      "reason": "우유 포함 확인이 없어 제외 조건에 맞을 가능성이 있고, 시큼한 쪽을 원할 때 선택지로 볼 수 있습니다."
    },
    {
      "menu_id": "lemonade",
      "temperature": "COLD",
      "reason": "공식 설명이 레몬의 산미를 특징으로 하며, 제공된 정보상 우유 포함 확인은 없습니다."
    },
    {
      "menu_id": "green_grape_ade",
      "temperature": "COLD",
      "reason": "제공된 정보상 우유 포함 확인이 없고, 상큼한 계열의 에이드로 분류되어 있습니다."
    }
  ],
  "questions": [],
  "missing_information": []
}
```

메뉴 이름: 레몬차, 레몬티, 레몬에이드, 청포도에이드

usage: {"input_tokens": 4347, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0}, "output_tokens": 208, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 4555}
비용 추정(USD): 0.00419625

## night_caffeine

밤에 마실 거라 잠 깨는 건 싫은데, 커피만 아니면 되나요?

**기존 추천**: ok / 1.714 ms

```json
{
  "menu_ids": [
    "espresso",
    "iced_americano",
    "cafe_latte"
  ]
}
```

메뉴 이름: 에스프레소, 아이스아메리카노, 카페라떼

**LLM 직접 추천**: error / 1788.57 ms

검증/실행 오류: UNVERIFIED_EXCLUSION

```json
{
  "status": "recommend",
  "recommendations": [
    {
      "menu_id": "lemon_tea",
      "temperature": "HOT",
      "reason": "공식 표기 카페인 0.0mg이며 HOT/COLD 가능. 밤에 마시기 무난한 선택입니다."
    },
    {
      "menu_id": "citron_tea",
      "temperature": "HOT",
      "reason": "공식 표기 카페인 0.0mg이며 HOT/COLD 가능. 잠 깨는 음료를 피하고 싶을 때 고르기 좋습니다."
    },
    {
      "menu_id": "lemonade",
      "temperature": "COLD",
      "reason": "공식 표기 카페인 0.0mg인 COLD 음료입니다. 다만 탄산이 있는 에이드로 설명됩니다."
    },
    {
      "menu_id": "green_grape_ade",
      "temperature": "COLD",
      "reason": "공식 표기 카페인 0.0mg인 COLD 음료입니다. 에이드 계열이라 커피는 아닙니다."
    }
  ],
  "questions": [],
  "missing_information": []
}
```

메뉴 이름: 레몬차, 유자차, 레몬에이드, 청포도에이드

usage: {"input_tokens": 4351, "input_tokens_details": {"cache_write_tokens": 0, "cached_tokens": 0}, "output_tokens": 215, "output_tokens_details": {"reasoning_tokens": 0}, "total_tokens": 4566}
비용 추정(USD): 0.00423075

## 비용 및 한계

usage가 있는 호출의 합계 추정: USD 0.024875.
모든 기록에 비용 추정이 있다.
계정 청구서/잔액과 다를 수 있으며 사용한 단가는 JSON에 기록한다.
기존 방식의 Pretuning 사전 생성 비용과 Whisper 비용은 제외한다.