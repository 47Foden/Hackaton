import { createHttpApi } from './http';
import { createMockApi } from './mock/createMockApi';

const mode = import.meta.env.VITE_API_MODE ?? 'mock';
if (mode !== 'mock' && mode !== 'http') throw new Error('VITE_API_MODE는 mock 또는 http여야 합니다.');
export const isMockApi = mode === 'mock';
const scenario = import.meta.env.VITE_MOCK_SCENARIO ?? 'success';
const scenarios = {
  success: {},
  empty: { menus: [] },
  'menu-error': { menuError: true },
  'order-rejected': { orderError: 'rejected' as const },
  'order-uncertain': { orderError: 'uncertain' as const },
};
if (isMockApi && !(scenario in scenarios)) throw new Error('지원하지 않는 mock 시나리오입니다.');
export const kioskApi = isMockApi
  ? createMockApi(scenarios[scenario as keyof typeof scenarios]) : createHttpApi();
