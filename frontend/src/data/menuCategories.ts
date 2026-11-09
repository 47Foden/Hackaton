import type { Menu } from './menuCatalog';

export const menuCategories: Record<string, readonly string[]> = {
  커피: ['에스프레소', '라떼', '콜드브루'],
  디카페인: ['에스프레소', '라떼', '콜드브루'],
  음료: ['에이드', '프라페', '스무디', '주스', '논커피라떼', '티'],
};

export function matchesCategory(menu: Menu, category: string, subcategory: string): boolean {
  if (menu.categories[0] !== category) return false;
  // 기존 API의 합쳐진 분류도 지원한다.
  const child = menu.categories[1] === '스무디/주스'
    ? (menu.name.includes('주스') ? '주스' : '스무디') : menu.categories[1];
  return child === subcategory;
}
