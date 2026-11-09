# 공통 메뉴 데이터

주문 카탈로그는 45개 메뉴를 제공한다. Pretuning의 기존 11개 평가 항목과 점수표는 별도로 관리한다. 레몬티와 레몬차는 동일한 공식 레몬차에 매핑되고 주문 ID는 각각 유지한다.

- `menu_data.py`: Pretuning의 평가 메뉴·카테고리·속성.
- `order_catalog.json`: 주문 메뉴 ID, 표시명, 카테고리와 옵션 프로필 연결.
- `order_option_profiles.json`: 모든 메뉴에 공통인 사이즈업과 음료 그룹별 옵션, 추가금 및 최대 선택 수.
- `menu_prices.json`: 기존과 같은 메뉴명 → 정수 원화 형식.
- `menu_price_sources.json`: 가격별 출처와 확인일. 확장 목록은 사용자 지정 가격이며, 기존 에스프레소와 레몬티는 이전 가격 출처를 유지한다.
- `menu_images.json`: 메뉴명 → HOT/COLD → 웹 이미지 경로. 키가 하나인 메뉴는 그 온도만 제공한다.
- `menu_image_sources.json`: 공식 상품명, 온도별 원본 이미지 URL, 공식 페이지와 확인일.
- `../frontend/public/images/menus/`: 공식 사이트에서 내려받은 원본 이미지 69개. 레몬티와 레몬차는 파일을 공유한다.

개발 Compose는 `frontend/public`과 `common`을 마운트한다. DB에 변경된 카탈로그를 반영하려면 마이그레이션과 시드를 실행한다.

- 브랜드 로고·색상·글꼴과 출처는 brand_assets.json, 프론트 적용 기준은 ../docs/frontend-design.md에 기록했다. 로고는 frontend/public/images/brand에 있다.

- menu_display.json: 프로젝트 초기 간편 메뉴 4종과 순서. 공식 인기/추천 자료가 아니며 가격·이미지 원본을 복제하지 않는다.
