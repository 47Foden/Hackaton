import type { ApiMenu, KioskApi } from '../contracts.ts';
import { ApiError } from '../errors.ts';
import { mockCatalog } from './catalog.ts';

interface MockOptions {
  delayMs?: number;
  menus?: ApiMenu[];
  menuError?: boolean;
  orderError?: 'rejected' | 'uncertain';
}

function wait(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(new DOMException('취소됨', 'AbortError')); return; }
    const abort = () => { clearTimeout(timer); reject(new DOMException('취소됨', 'AbortError')); };
    const timer = setTimeout(() => { signal?.removeEventListener('abort', abort); resolve(); }, ms);
    signal?.addEventListener('abort', abort, { once: true });
  });
}

/** 실제 어댑터와 동일한 JSON 계약. 저장·결제 없이 개발용 번호만 반환한다. */
export function createMockApi(options: MockOptions = {}): KioskApi {
  const menus = structuredClone(options.menus ?? mockCatalog);
  let sequence = 0;
  return {
    async getMenus(signal) {
      await wait(options.delayMs ?? 350, signal);
      if (options.menuError) throw new ApiError('메뉴를 불러오지 못했어요.', 503, 'CATALOG_UNAVAILABLE');
      return { menus: structuredClone(menus) };
    },
    async createOrder(request, signal) {
      await wait(options.delayMs ?? 350, signal);
      const keys = Object.keys(request);
      if (typeof request.menu_id !== 'string' || !request.menu_id.trim()
        || keys.length !== 3 || keys.some(key => !['menu_id', 'temperature', 'service_type'].includes(key))
        || !['HOT', 'COLD'].includes(request.temperature) || !['DINE_IN', 'TAKEOUT'].includes(request.service_type)) {
        throw new ApiError('입력 내용을 확인해 주세요.', 422, 'VALIDATION_ERROR');
      }
      const menu = menus.find(item => item.menu_id === request.menu_id);
      if (!menu) throw new ApiError('메뉴를 찾을 수 없어요.', 404, 'MENU_NOT_FOUND');
      if (!menu.is_available) throw new ApiError('판매 중지된 메뉴예요.', 409, 'MENU_UNAVAILABLE');
      if (!menu.available_temperatures.includes(request.temperature)) throw new ApiError('제공하지 않는 온도예요.', 422, 'INVALID_OPTION');
      if (options.orderError) throw new ApiError('주문 처리를 확인하지 못했어요.',
        options.orderError === 'rejected' ? 409 : 503,
        options.orderError === 'rejected' ? 'MENU_UNAVAILABLE' : 'ORDER_STORAGE_UNAVAILABLE',
        options.orderError === 'uncertain');
      const number = `DEV-${String(++sequence).padStart(4, '0')}`;
      return { ...request, order_id: number, order_number: number, menu_name: menu.name,
        quantity: 1, total_price_krw: menu.price_krw, created_at: new Date().toISOString() };
    },
  };
}
