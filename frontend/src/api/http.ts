import type { KioskApi, MenusResponse, OrderResponse } from './contracts.ts';
import { ApiError } from './errors.ts';

export function createHttpApi(transport: typeof fetch = fetch): KioskApi {
  async function request<T>(path: string, init: RequestInit, isOrder = false): Promise<T> {
    try {
      const timeout = AbortSignal.timeout(15_000);
      const signal = init.signal ? AbortSignal.any([init.signal, timeout]) : timeout;
      const response = await transport(`/api/${path}`, { ...init, signal });
      const body = await response.json().catch(error => {
        if (isOrder && !response.ok) return null;
        throw error;
      });
      if (!response.ok) {
        const detail = body?.detail;
        const message = typeof detail === 'string' ? detail
          : Array.isArray(detail) ? '입력 내용을 확인해 주세요.'
          : detail?.message ?? '요청을 처리하지 못했어요.';
        throw new ApiError(message, response.status, detail?.code ?? 'HTTP_ERROR',
          isOrder && ![404, 409, 422].includes(response.status));
      }
      if (isOrder && (![200, 201].includes(response.status)
        || typeof body?.order_number !== 'string' || !/^[1-9][0-9]*$/.test(body.order_number)
        || body.order_id !== body.order_number
        || typeof body?.menu_name !== 'string' || typeof body?.menu_id !== 'string'
        || !['HOT', 'COLD'].includes(body?.temperature) || !['DINE_IN', 'TAKEOUT'].includes(body?.service_type)
        || body?.quantity !== 1 || !Number.isInteger(body?.total_price_krw) || body.total_price_krw < 0
        || (body?.selected_options !== undefined && (!Array.isArray(body.selected_options)
          || body.selected_options.some((option: unknown) => {
            if (!option || typeof option !== 'object') return true;
            const { id, label, price_delta_krw } = option as Record<string, unknown>;
            return typeof id !== 'string' || typeof label !== 'string'
              || typeof price_delta_krw !== 'number' || !Number.isInteger(price_delta_krw) || price_delta_krw < 0;
          })))
        || typeof body?.created_at !== 'string' || Number.isNaN(Date.parse(body.created_at)))) {
        throw new ApiError('주문 응답을 확인할 수 없어요.', response.status, 'INVALID_RESPONSE', true);
      }
      return body as T;
    } catch (error) {
      if (error instanceof ApiError) throw error;
      throw new ApiError('서버 응답을 확인하지 못했어요.', 0, 'NETWORK_ERROR', isOrder);
    }
  }
  return {
    getMenus: signal => request<MenusResponse>('menus', { signal }),
    createOrder: (order, signal) => request<OrderResponse>('orders', {
      method: 'POST', signal, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(order),
    }, true),
  };
}
