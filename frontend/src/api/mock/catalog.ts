import metadata from '../../../../common/order_catalog.json' with { type: 'json' };
import prices from '../../../../common/menu_prices.json' with { type: 'json' };
import images from '../../../../common/menu_images.json' with { type: 'json' };
import display from '../../../../common/menu_display.json' with { type: 'json' };
import options from '../../../../common/order_option_profiles.json' with { type: 'json' };
import type { ApiMenu, MenuOptionGroup, Temperature } from '../contracts.ts';

const pricesByName: Record<string, number> = prices;
const imagesByName: Record<string, Partial<Record<Temperature, string>>> = images;
const profiles: Record<string, MenuOptionGroup[]> = options.profiles;

export const mockCatalog: ApiMenu[] = metadata.map((menu, index) => {
  const variants = imagesByName[menu.name];
  const temperatures = (['HOT', 'COLD'] as const).filter(value => variants[value]);
  const option_groups = [...options.common, ...profiles[menu.option_profile]];
  return {
    menu_id: menu.menu_id, name: menu.name, categories: menu.categories, price_krw: pricesByName[menu.name],
    available_temperatures: temperatures,
    variants: temperatures.map(temperature => ({ temperature, image_url: variants[temperature]!, option_groups })),
    image_url: (variants.COLD ?? variants.HOT)!,
    is_available: true, display_order: index + 1,
    is_featured: display.simplified_menu_names.includes(menu.name),
  };
});
