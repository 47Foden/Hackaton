import { useEffect, useReducer, useRef } from 'react';
import type { CreateOrderRequest, KioskApi } from '../api/contracts';
import { asApiError } from '../api/errors';
import { initialOrderState, orderReducer } from '../state/order';

export function useOrderFlow(api: KioskApi) {
  const [order, dispatch] = useReducer(orderReducer, initialOrderState);
  const pending = useRef<AbortController | null>(null);
  const submittedRequest = useRef<CreateOrderRequest | null>(null);
  useEffect(() => () => { pending.current?.abort(); }, []);

  async function confirm() {
    if (order.stage !== 'review' || pending.current || order.error?.kind === 'conflict') return;
    const controller = new AbortController();
    const request = submittedRequest.current ??= {
      request_id: crypto.randomUUID(), menu_id: order.draft.menu.id,
      temperature: order.draft.temperature, service_type: order.draft.serviceType,
    };
    pending.current = controller;
    dispatch({ type: 'submit' });
    try {
      const result = await api.createOrder(request, controller.signal);
      if (!controller.signal.aborted) dispatch({ type: 'submitted', result });
    } catch (error) {
      if (!controller.signal.aborted) {
        const failure = asApiError(error, true);
        const kind = failure.code === 'IDEMPOTENCY_CONFLICT' ? 'conflict' : failure.uncertain ? 'uncertain' : 'rejected';
        dispatch({ type: 'failed', error: { message: failure.message, kind } });
      }
    } finally {
      if (pending.current === controller) pending.current = null;
    }
  }
  return { order, dispatch, confirm };
}
