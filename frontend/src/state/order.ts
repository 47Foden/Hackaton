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
  | { stage: 'customization'; menu: Menu; temperature: Temperature; selectedOptions?: MenuOption[]; voiceOptions?: VoiceOptions }
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

type SelectionState = Extract<OrderState, { stage: 'temperature' | 'customization' | 'service_type' }>;

// A supplied snapshot is authoritative, including explicit clears. Preserve
// completed touch choices when no corresponding voice field was supplied.
function selectionOptions(state: SelectionState, snapshot?: VoiceOptions): VoiceOptions {
  const options = { ...(snapshot ?? state.voiceOptions ?? {}) };
  if (state.stage !== 'temperature' && options.temperature === undefined
      && !options.unresolved_fields?.includes('temperature')) options.temperature = state.temperature;
  if (state.stage === 'service_type' && options.customization === undefined) {
    options.customization = selectedCustomization(state.selectedOptions.map(choice => choice.id));
  }
  return options;
}

// All selection actions use the same ordered decision: temperature ->
// customization -> service type -> review. Keep original intents in state so
// a failed validation at one temperature does not poison the next validation.
export function nextOrderStage(menu: Menu, options: VoiceOptions = {}): OrderState {
  const temperature = options.temperature ?? (menu.temperatures.length === 1 ? menu.temperatures[0] : undefined);
  if (!temperature || !menu.temperatures.includes(temperature) || options.unresolved_fields?.includes('temperature')) {
    return { stage: 'temperature', menu, voiceOptions: options };
  }
  const validated = validateVoiceOptions(options, menu, temperature);
  const customization = validated.customization;
  const groups = menu.optionGroups?.[temperature] ?? [];
  const selectedOptions = resolveOrderOptions(groups, customization?.option_ids ?? []);
  if ((customization && (customization.status !== 'resolved' || !selectedOptions))
      || (!customization && groups.length > 0)) {
    return { stage: 'customization', menu, temperature, selectedOptions: selectedOptions ?? [], voiceOptions: options };
  }
  const serviceType = options.service_type;
  if (!serviceType || !['DINE_IN', 'TAKEOUT'].includes(serviceType) || options.unresolved_fields?.includes('service_type')) {
    return { stage: 'service_type', menu, temperature, selectedOptions: selectedOptions ?? [], voiceOptions: options };
  }
  return { stage: 'review', draft: { menu, temperature, serviceType, selectedOptions: selectedOptions ?? [] } };
}

// 화면 밖에서 들어오는 입력도 현재 단계와 제공 옵션에 맞을 때만 적용한다.
export function orderReducer(state: OrderState, action: OrderAction): OrderState {
  switch (action.type) {
    case 'apply_voice_options': {
      if (state.stage !== 'temperature' && state.stage !== 'customization' && state.stage !== 'service_type') return state;
      return nextOrderStage(state.menu, selectionOptions(state, action.voiceOptions));
    }
    case 'select_menu': {
      if (state.stage !== 'menu' || !action.menu.available || action.menu.temperatures.length === 0) return state;
      return nextOrderStage(action.menu, action.voiceOptions);
    }
    case 'set_temperature':
      return state.stage === 'temperature' && state.menu.temperatures.includes(action.temperature)
        ? nextOrderStage(state.menu, mergeVoiceOptions(selectionOptions(state, action.voiceOptions), { temperature: action.temperature }))
        : state;

    case 'set_options': {
      if (state.stage !== 'customization') return state;
      const selectedOptions = resolveOrderOptions(state.menu.optionGroups?.[state.temperature] ?? [], action.ids);
      if (!selectedOptions) return state;
      return nextOrderStage(state.menu, { ...selectionOptions(state, action.voiceOptions),
        customization: selectedCustomization(action.ids) });
    }
    case 'set_service_type':
      return state.stage === 'service_type' && ['DINE_IN', 'TAKEOUT'].includes(action.serviceType)
        ? nextOrderStage(state.menu, mergeVoiceOptions(selectionOptions(state, action.voiceOptions), { service_type: action.serviceType }))
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
