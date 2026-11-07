import type { KioskApi } from './contracts.ts';
import { createHttpApi } from './http.ts';
import { createMockApi, type MockOptions } from './mock/createMockApi.ts';
import { ApiError } from './errors.ts';

export type ApiMode = 'http' | 'mock';

interface ApiOptions {
  menuMode?: ApiMode;
  orderMode?: ApiMode;
  transport?: typeof fetch;
  mock?: MockOptions;
}

/** 메뉴 조회와 주문 저장의 연결 대상을 독립적으로 선택한다. */
export function createKioskApi({ menuMode = 'http', orderMode = 'http', transport, mock }: ApiOptions = {}): KioskApi {
  const http = createHttpApi(transport);
  const developmentApi = createMockApi(mock);
  let catalogueReady = menuMode === 'mock';
  return {
    async getMenus(signal) {
      if (menuMode === 'http') catalogueReady = false;
      const response = await (menuMode === 'http' ? http : developmentApi).getMenus(signal);
      // 개발용 주문도 실제 조회된 가격·판매 상태·온도를 검증한다.
      if (menuMode === 'http' && orderMode === 'mock' && !signal?.aborted) developmentApi.setMenus(response.menus);
      if (!signal?.aborted) catalogueReady = true;
      return response;
    },
    createOrder(request, signal) {
      if (orderMode === 'mock' && !catalogueReady) {
        return Promise.reject(new ApiError('메뉴를 먼저 불러와 주세요.', 409, 'CATALOG_NOT_LOADED'));
      }
      return (orderMode === 'http' ? http : developmentApi).createOrder(request, signal);
    },
  };
}
