import type { Menu, Temperature } from '../data/menuCatalog';
import type { MenuOption, OrderResponse, ServiceType } from '../api/contracts';
import { resolveOrderOptions } from './orderOptions.ts';
import { mergeVoiceOptions, validateVoiceOptions, selectedCustomization } from './voiceOptions.ts';
import type { VoiceOptions } from './voiceOptions.ts';

export type { ServiceType } from '../api/contracts';
export interface OrderDraft { menu: Menu; temperature: Temperature; serviceType: ServiceType; selectedOptions: MenuOption[]; }
export interface OrderFailure { message: string; kind: 'rejected' | 'uncertain' | 'conflict'; }
export type OrderState =
  | { stage: 'menu' }
  | { stage: 'temperature'; menu: Menu; voiceOptions?: VoiceOptions }
  | { stage: 'customization'; menu: Menu; temperature: Temperature; voiceOptions?: VoiceOptions }
  | { stage: 'service_type'; menu: Menu; temperature: Temperature; selectedOptions: MenuOption[]; voiceOptions?: VoiceOptions }
  | { stage: 'review'; draft: OrderDraft; error?: OrderFailure }
  | { stage: 'submitting'; draft: OrderDraft }
  | { stage: 'complete'; draft: OrderDraft; result: OrderResponse };

export type OrderAction =
  | { type: 'select_menu'; menu: Menu; voiceOptions?: VoiceOptions }
  | { type: 'set_temperature'; temperature: Temperature; voiceOptions?: VoiceOptions }
  | { type: 'set_options'; ids: string[]; voiceOptions?: VoiceOptions }
  | { type: 'set_service_type'; serviceType: ServiceType; voiceOptions?: VoiceOptions }
  | { type: 'apply_voice_options'; voiceOptions: VoiceOptions }
  | { type: 'submit' }
  | { type: 'submitted'; result: OrderResponse }
  | { type: 'failed'; error: OrderFailure };

export type OrderSelection =
  | { type: 'select_menu'; menuId: string }
  | Extract<OrderAction, { type: 'set_temperature' | 'set_service_type' }>;

export const initialOrderState: OrderState = { stage: 'menu' };

function afterOptions(menu: Menu, temperature: Temperature, selectedOptions: MenuOption[], voiceOptions?: VoiceOptions): OrderState {
  return voiceOptions?.service_type && !voiceOptions.unresolved_fields?.includes('service_type')
    ? { stage: 'review', draft: { menu, temperature, selectedOptions, serviceType: voiceOptions.service_type } }
    : { stage: 'service_type', menu, temperature, selectedOptions, ...(voiceOptions ? { voiceOptions } : {}) };
}

function afterTemperature(menu: Menu, temperature: Temperature, options?: VoiceOptions): OrderState {
  const voiceOptions = options ? validateVoiceOptions(options, menu, temperature) : undefined;
  if (voiceOptions?.unresolved_fields?.includes('temperature')) return { stage: 'temperature', menu, voiceOptions };
  const c = voiceOptions?.customization;
  if (c?.status === 'resolved') {
    const choices = resolveOrderOptions(menu.optionGroups?.[temperature] ?? [], c.option_ids);
    if (choices) return afterOptions(menu, temperature, choices, voiceOptions);
  }
  return menu.optionGroups?.[temperature]?.length || c?.status === 'needs_clarification'
    ? { stage: 'customization', menu, temperature, ...(voiceOptions ? { voiceOptions } : {}) }
    : afterOptions(menu, temperature, [], voiceOptions);
}

// 화면 밖에서 들어오는 입력도 현재 단계와 제공 옵션에 맞을 때만 적용한다.
export function orderReducer(state: OrderState, action: OrderAction): OrderState {
  switch (action.type) {
    case 'apply_voice_options': {
      if (state.stage !== 'customization' && state.stage !== 'service_type') return state;
      // The voice screen submits the complete session snapshot, including clears.
      const options = action.voiceOptions;
      const temperature = options.temperature ?? state.temperature;
      if (!state.menu.temperatures.includes(temperature)) return { stage: 'temperature', menu: state.menu, voiceOptions: options };
      return afterTemperature(state.menu, temperature, options);
    }
    case 'select_menu': {
      if (state.stage !== 'menu' || !action.menu.available || action.menu.temperatures.length === 0) return state;
      const [temperature] = action.menu.temperatures;
      if (action.voiceOptions) {
        const voiceOptions = validateVoiceOptions(action.voiceOptions, action.menu);
        if (voiceOptions.unresolved_fields?.includes('temperature')) return { stage: 'temperature', menu: action.menu, voiceOptions };
        const chosen = voiceOptions.temperature ?? (action.menu.temperatures.length === 1 ? temperature : undefined);
        return chosen ? afterTemperature(action.menu, chosen, voiceOptions)
          : { stage: 'temperature', menu: action.menu, voiceOptions };
      }
      return action.menu.temperatures.length === 1
        ? afterTemperature(action.menu, temperature)
        : { stage: 'temperature', menu: action.menu };
    }
    case 'set_temperature':
      return state.stage === 'temperature' && state.menu.temperatures.includes(action.temperature)
        ? afterTemperature(state.menu, action.temperature, state.voiceOptions || action.voiceOptions
          ? mergeVoiceOptions(action.voiceOptions ?? state.voiceOptions ?? {}, { temperature: action.temperature }) : undefined)
        : state;

    case 'set_options': {
      if (state.stage !== 'customization') return state;
      const selectedOptions = resolveOrderOptions(state.menu.optionGroups[state.temperature] ?? [], action.ids);
      if (!selectedOptions) return state;
      const options = state.voiceOptions || action.voiceOptions
        ? { ...mergeVoiceOptions(state.voiceOptions ?? {}, action.voiceOptions), customization: selectedCustomization(action.ids) } : undefined;
      return afterOptions(state.menu, state.temperature, selectedOptions, options);
    }
    case 'set_service_type':
      return state.stage === 'service_type' && ['DINE_IN', 'TAKEOUT'].includes(action.serviceType)
        ? action.voiceOptions?.customization
          ? afterTemperature(state.menu, state.temperature, mergeVoiceOptions(
            mergeVoiceOptions(state.voiceOptions ?? {}, action.voiceOptions), { service_type: action.serviceType }))
          : { stage: 'review', draft: { menu: state.menu, temperature: state.temperature,
            serviceType: action.serviceType, selectedOptions: state.selectedOptions } }
        : state;
    case 'submit':
      return state.stage === 'review' && state.error?.kind !== 'conflict' ? { stage: 'submitting', draft: state.draft } : state;
    case 'submitted':
      return state.stage === 'submitting' ? { stage: 'complete', draft: state.draft, result: action.result } : state;
    case 'failed':
      return state.stage === 'submitting' ? { stage: 'review', draft: state.draft, error: action.error } : state;
  }
}

export const temperatureLabels: Record<Temperature, string> = { HOT: '따뜻하게', COLD: '차갑게' };
export const serviceTypeLabels: Record<ServiceType, string> = { DINE_IN: '매장에서', TAKEOUT: '포장해서' };
