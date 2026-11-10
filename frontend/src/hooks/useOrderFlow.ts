import { useEffect, useReducer, useRef, useState } from 'react';
import type { CreateOrderRequest, KioskApi, ServiceType } from '../api/contracts';
import { asApiError } from '../api/errors';
import { initialOrderState, orderReducer, sessionOrderReducer, type OrderDraft } from '../state/order';

export function useOrderFlow(api: KioskApi, serviceType: ServiceType) {
  const [order, dispatch] = useReducer((state: Parameters<typeof orderReducer>[0], action: Parameters<typeof orderReducer>[1] | {type: 'continue'}) => sessionOrderReducer(state, action, serviceType), initialOrderState);
  const [cart, setCart] = useState<OrderDraft[]>([]);
  const [quantity, setQuantity] = useState(1);
  const items = 'draft' in order ? [...cart, {...order.draft, quantity}].map(item => ({...item, serviceType: order.draft.serviceType})) : cart;
  function deferService() {
    if (order.stage !== 'service_type' || submittedRequest.current) return;
    setCart([...cart, {menu: order.menu, temperature: order.temperature,
      selectedOptions: order.selectedOptions, quantity, serviceType: 'DINE_IN'}]);
    setQuantity(1); dispatch({type: 'continue'});
  }
  function continueOrder() {
    if (order.stage !== 'review' || submittedRequest.current) return;
    setCart(items); setQuantity(1); dispatch({type: 'continue'});
  }
  function changeQuantity(index: number, value: number) {
    if (order.stage !== 'review' || submittedRequest.current || value < 1 || value > 99) return;
    if (index === cart.length) setQuantity(value);
    else setCart(cart.map((item, i) => i === index ? {...item, quantity: value} : item));
  }
  const pending = useRef<AbortController | null>(null);
  const submittedRequest = useRef<CreateOrderRequest | null>(null);
  useEffect(() => () => { pending.current?.abort(); }, []);

  async function confirm() {
    if (order.stage !== 'review' || pending.current || order.error?.kind === 'conflict') return;
    const controller = new AbortController();
    const optionIds = order.draft.selectedOptions.map(choice => choice.id);
    const request = submittedRequest.current ??= {
      items: items.map(item => ({menu_id: item.menu.id, temperature: item.temperature, service_type: item.serviceType, quantity: item.quantity ?? 1, option_ids: item.selectedOptions.map(o => o.id)})),
      request_id: crypto.randomUUID(), menu_id: order.draft.menu.id,
      temperature: order.draft.temperature, service_type: order.draft.serviceType,
      ...(optionIds.length ? { option_ids: optionIds } : {}),
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
  return { order, dispatch, confirm, items, continueOrder, deferService, changeQuantity, quantity, setQuantity, locked: !!submittedRequest.current };
}
