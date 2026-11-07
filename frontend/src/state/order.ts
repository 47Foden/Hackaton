import type { Menu, Temperature } from '../data/menuCatalog';

export type ServiceType = 'DINE_IN' | 'TAKEOUT';
export interface OrderDraft { menu: Menu; temperature: Temperature; serviceType: ServiceType; }
export type OrderState =
  | { stage: 'menu' }
  | { stage: 'temperature'; menu: Menu }
  | { stage: 'service_type'; menu: Menu; temperature: Temperature }
  | { stage: 'review'; draft: OrderDraft }
  | { stage: 'complete'; draft: OrderDraft };

export type OrderAction =
  | { type: 'select_menu'; menu: Menu }
  | { type: 'set_temperature'; temperature: Temperature }
  | { type: 'set_service_type'; serviceType: ServiceType }
  | { type: 'confirm' };

export const initialOrderState: OrderState = { stage: 'menu' };

// 화면 밖에서 들어오는 입력도 현재 단계와 제공 옵션에 맞을 때만 적용한다.
export function orderReducer(state: OrderState, action: OrderAction): OrderState {
  switch (action.type) {
    case 'select_menu': {
      if (state.stage !== 'menu' || action.menu.temperatures.length === 0) return state;
      const [temperature] = action.menu.temperatures;
      return action.menu.temperatures.length === 1
        ? { stage: 'service_type', menu: action.menu, temperature }
        : { stage: 'temperature', menu: action.menu };
    }
    case 'set_temperature':
      return state.stage === 'temperature' && state.menu.temperatures.includes(action.temperature)
        ? { stage: 'service_type', menu: state.menu, temperature: action.temperature }
        : state;
    case 'set_service_type':
      return state.stage === 'service_type' && ['DINE_IN', 'TAKEOUT'].includes(action.serviceType)
        ? { stage: 'review', draft: { menu: state.menu, temperature: state.temperature, serviceType: action.serviceType } }
        : state;
    case 'confirm':
      return state.stage === 'review' ? { stage: 'complete', draft: state.draft } : state;
  }
}

export const temperatureLabels: Record<Temperature, string> = { HOT: '따뜻하게', COLD: '차갑게' };
export const serviceTypeLabels: Record<ServiceType, string> = { DINE_IN: '매장에서', TAKEOUT: '포장해서' };
