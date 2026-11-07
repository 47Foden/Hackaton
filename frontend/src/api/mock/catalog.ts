import prices from '../../../../common/menu_prices.json' with { type: 'json' };
import images from '../../../../common/menu_images.json' with { type: 'json' };
import display from '../../../../common/menu_display.json' with { type: 'json' };
import type { ApiMenu, Temperature } from '../contracts.ts';

// API 명세의 고정 ID·카테고리 매핑. 가격과 이미지는 common에서만 읽는다.
const metadata: [string, keyof typeof prices, string[]][] = [
  ['peach_iced_tea', '복숭아 아이스티', ['티']],
  ['lemon_tea_alias', '레몬티', ['티']],
  ['iced_americano', '아이스아메리카노', ['커피']],
  ['lemonade', '레몬에이드', ['에이드']],
  ['strawberry_latte', '딸기라떼', ['논커피라떼', '라떼']],
  ['green_grape_ade', '청포도에이드', ['에이드']],
  ['cafe_latte', '카페라떼', ['커피', '라떼']],
  ['lemon_tea', '레몬차', ['티']],
  ['citron_tea', '유자차', ['티']],
  ['espresso', '에스프레소', ['커피']],
  ['green_tea_latte', '녹차라떼', ['논커피라떼', '라떼']],
];

export const mockCatalog: ApiMenu[] = metadata.map(([id, name, categories], index) => {
  const variants: Partial<Record<Temperature, string>> = images[name];
  const temperatures = (['HOT', 'COLD'] as const).filter(value => variants[value]);
  return {
    menu_id: id, name, categories, price_krw: prices[name],
    available_temperatures: temperatures,
    variants: temperatures.map(temperature => ({ temperature, image_url: variants[temperature]! })),
    image_url: (variants.COLD ?? variants.HOT)!,
    is_available: true, display_order: index + 1,
    is_featured: display.simplified_menu_names.includes(name),
  };
});
