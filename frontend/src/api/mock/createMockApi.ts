import type { ApiMenu, KioskApi, OrderResponse } from '../contracts.ts';
import { ApiError } from '../errors.ts';
import { mockCatalog } from './catalog.ts';
import { resolveOrderOptions } from '../../state/orderOptions.ts';

export interface MockOptions {
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
export function createMockApi(options: MockOptions = {}): KioskApi & { setMenus(menus: ApiMenu[]): void } {
  let menus = structuredClone(options.menus ?? mockCatalog);
  let sequence = 0;
  const orders = new Map<string, OrderResponse>();
  return {
    setMenus(nextMenus) {
      menus = structuredClone(nextMenus);
    },
    async getMenus(signal) {
      await wait(options.delayMs ?? 350, signal);
      if (options.menuError) throw new ApiError('메뉴를 불러오지 못했어요.', 503, 'CATALOG_UNAVAILABLE');
      return { menus: structuredClone(menus) };
    },
    async createOrder(request, signal) {
      await wait(options.delayMs ?? 350, signal);
      const keys = Object.keys(request);
      const { request_id, menu_id, temperature, service_type, option_ids = [] } = request;
      if (typeof request_id !== 'string' || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(request_id)
        || typeof menu_id !== 'string' || !menu_id || menu_id.includes('\0')
        || keys.some(key => !['request_id', 'menu_id', 'temperature', 'service_type', 'option_ids'].includes(key))
        || !Array.isArray(option_ids) || option_ids.length > 32
        || option_ids.some(id => typeof id !== 'string' || !/^[a-z_]+:[a-z_]+$/.test(id))
        || !['HOT', 'COLD'].includes(temperature) || !['DINE_IN', 'TAKEOUT'].includes(service_type)) {
        throw new ApiError('입력 내용을 확인해 주세요.', 422, 'VALIDATION_ERROR');
      }
      const key = request_id.toLowerCase();
      const saved = orders.get(key);
      if (saved) {
        const savedIds = saved.selected_options?.map(choice => choice.id).sort() ?? [];
        if (saved.menu_id !== menu_id || saved.temperature !== temperature || saved.service_type !== service_type
          || savedIds.join(',') !== [...option_ids].sort().join(',')) {
          throw new ApiError('같은 요청 ID로 접수된 주문의 내용이 다릅니다.', 409, 'IDEMPOTENCY_CONFLICT');
        }
        return structuredClone(saved);
      }
      const menu = menus.find(item => item.menu_id === menu_id);
      if (!menu) throw new ApiError('메뉴를 찾을 수 없어요.', 404, 'MENU_NOT_FOUND');
      if (!menu.is_available) throw new ApiError('판매 중지된 메뉴예요.', 409, 'MENU_UNAVAILABLE');
      const variant = menu.variants.find(item => item.temperature === temperature);
      const selected = variant && resolveOrderOptions(variant.option_groups ?? [], option_ids);
      if (!selected) throw new ApiError('선택할 수 없는 온도 또는 추가 옵션입니다.', 422, 'INVALID_OPTION');
      if (options.orderError === 'rejected') throw new ApiError('주문이 거부됐어요.', 409, 'MENU_UNAVAILABLE');
      const number = `DEV-${String(++sequence).padStart(4, '0')}`;
      const result: OrderResponse = { menu_id, temperature, service_type, order_id: number, order_number: number, menu_name: menu.name,
        quantity: 1, selected_options: selected,
        total_price_krw: menu.price_krw + selected.reduce((sum, choice) => sum + choice.price_delta_krw, 0),
        created_at: new Date().toISOString() };
      orders.set(key, result);
      if (options.orderError === 'uncertain') {
        throw new ApiError('주문 처리를 확인하지 못했어요.', 503, 'ORDER_STORAGE_UNAVAILABLE', true);
      }
      return structuredClone(result);
    },
  };
}
