import type { OrderSelection, OrderState } from '../state/order';

// Deterministic fixtures for checking the voice-to-order path after recording ends.
export const mockVoiceSelections: Partial<Record<OrderState['stage'], OrderSelection>> = {
  menu: { type: 'select_menu', menuId: 'cafe_latte' },
  temperature: { type: 'set_temperature', temperature: 'HOT' },
  service_type: { type: 'set_service_type', serviceType: 'TAKEOUT' },
};
