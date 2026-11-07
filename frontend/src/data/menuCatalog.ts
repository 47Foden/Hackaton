import prices from '../../../common/menu_prices.json';
import images from '../../../common/menu_images.json';
import display from '../../../common/menu_display.json';

export type Temperature = 'HOT' | 'COLD';

export interface Menu {
  name: string;
  price: number;
  imageUrl: string;
  temperatures: Temperature[];
  imageUrls: Partial<Record<Temperature, string>>;
}

// API 연결 전에는 common을 직접 참조해 가격과 이미지 사본을 만들지 않는다.
export const menuCatalog: Menu[] = Object.entries(prices).map(([name, price]) => {
  const variants: Partial<Record<'HOT' | 'COLD', string>> = images[name as keyof typeof images];
  return { name, price, imageUrl: (variants.COLD ?? variants.HOT)!,
    temperatures: Object.keys(variants) as Temperature[], imageUrls: variants };
});

// 설정 순서를 유지하고 알 수 없는 이름과 중복은 제외한다. 빈 목록이면 전체를 표시한다.
export const simplifiedMenuCatalog: Menu[] = [...new Set(display.simplified_menu_names)]
  .flatMap(name => {
    const menu = menuCatalog.find(item => item.name === name);
    return menu ? [menu] : [];
  });
