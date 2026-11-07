import { createKioskApi, type ApiMode } from './createKioskApi';

function mode(value: string | undefined, fallback: ApiMode): ApiMode {
  const selected = value?.trim() || fallback;
  if (selected !== 'mock' && selected !== 'http') throw new Error('API 모드는 mock 또는 http여야 합니다.');
  return selected;
}

// 개별 모드가 기존 일괄 VITE_API_MODE보다 우선한다.
const legacy = import.meta.env.VITE_API_MODE?.trim();
const menuMode = mode(import.meta.env.VITE_MENU_API_MODE || legacy, 'http');
const orderMode = mode(import.meta.env.VITE_ORDER_API_MODE || legacy, 'http');
export const isMockMenuApi = menuMode === 'mock';
export const isMockOrderApi = orderMode === 'mock';
const scenario = import.meta.env.VITE_MOCK_SCENARIO ?? 'success';
const scenarios = {
  success: {},
  empty: { menus: [] },
  'menu-error': { menuError: true },
  'order-rejected': { orderError: 'rejected' as const },
  'order-uncertain': { orderError: 'uncertain' as const },
};
if ((isMockMenuApi || isMockOrderApi) && !(scenario in scenarios)) throw new Error('지원하지 않는 mock 시나리오입니다.');
export const kioskApi = createKioskApi({ menuMode, orderMode, mock: scenarios[scenario as keyof typeof scenarios] });
