import { useEffect, useReducer, useRef } from 'react';
import type { KioskApi } from '../api/contracts';
import { asApiError } from '../api/errors';
import { initialOrderState, orderReducer } from '../state/order';

export function useOrderFlow(api: KioskApi) {
  const [order, dispatch] = useReducer(orderReducer, initialOrderState);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => { pending.current?.abort(); }, []);

  async function confirm() {
    if (order.stage !== 'review' || pending.current || order.error?.uncertain) return;
    const controller = new AbortController();
    pending.current = controller;
    dispatch({ type: 'submit' });
    try {
      const result = await api.createOrder({ menu_id: order.draft.menu.id,
        temperature: order.draft.temperature, service_type: order.draft.serviceType }, controller.signal);
      if (!controller.signal.aborted) dispatch({ type: 'submitted', result });
    } catch (error) {
      if (!controller.signal.aborted) {
        const failure = asApiError(error, true);
        dispatch({ type: 'failed', error: { message: failure.message, uncertain: failure.uncertain } });
      }
    } finally {
      if (pending.current === controller) pending.current = null;
    }
  }
  return { order, dispatch, confirm };
}
