import type { ApiMenu, MenuOptionGroup, Temperature } from '../api/contracts';
export type { Temperature } from '../api/contracts';

export interface Menu {
  id: string;
  name: string;
  categories: string[];
  price: number;
  imageUrl: string;
  temperatures: Temperature[];
  imageUrls: Partial<Record<Temperature, string>>;
  optionGroups: Partial<Record<Temperature, MenuOptionGroup[]>>;
  available: boolean;
  featured: boolean;
}

// API JSON을 화면 모델로 변환한다. 여기서는 요청하거나 common을 직접 읽지 않는다.
export function toMenu(menu: ApiMenu): Menu {
  return {
    id: menu.menu_id, name: menu.name, price: menu.price_krw, categories: menu.categories,
    imageUrl: menu.image_url, temperatures: menu.available_temperatures,
    imageUrls: Object.fromEntries(menu.variants.map(item => [item.temperature, item.image_url])),
    optionGroups: Object.fromEntries(menu.variants.map(item => [item.temperature, item.option_groups ?? []])),
    available: menu.is_available, featured: menu.is_featured,
  };
}
