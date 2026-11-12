import { useEffect, useRef, useState } from 'react';
import type { CreateOrderRequest, KioskApi, ServiceType } from '../api/contracts';
import { asApiError } from '../api/errors';
import { initialOrderState, sessionOrderReducer, type OrderDraft, type OrderState, type OrderAction } from '../state/order';

export function useOrderFlow(api: KioskApi, serviceType: ServiceType, captureNavigation?: () => (() => void)) {
  const [order, setOrder] = useState<OrderState>(initialOrderState);
  const orderRef = useRef(order);
  orderRef.current = order;
  const history = useRef<{order: OrderState; cart: OrderDraft[]; quantity: number; restore?: () => void}[]>([]);
  const [cart, setCart] = useState<OrderDraft[]>([]);
  const [quantity, setQuantity] = useState(1);
  const pending = useRef<AbortController | null>(null);
  const submittedRequest = useRef<CreateOrderRequest | null>(null);
  function checkpoint(previous = orderRef.current) {
    history.current.push({order: previous, cart, quantity, restore: captureNavigation?.()});
  }
  function dispatch(action: OrderAction | {type: 'continue'}, record = true) {
    const previous = orderRef.current;
    const next = sessionOrderReducer(previous, action, serviceType);
    if (record && next.stage !== previous.stage && !['submit', 'submitted', 'failed'].includes(action.type)) {
      let saved = previous;
      if (previous.stage === 'customization' && action.type === 'set_options') {
        saved = {...previous, voiceOptions: {...previous.voiceOptions,
          customization: {status: 'resolved', option_ids: action.ids, intents: [], unresolved: []}}};
      }
      checkpoint(saved);
    }
    orderRef.current = next; setOrder(next);
  }
  const canBack = history.current.length > 0 && !submittedRequest.current &&
    !['submitting', 'complete'].includes(order.stage);
  function back() {
    if (!canBack) return;
    const previous = history.current.pop();
    if (!previous) return;
    const sameItem = cart.length === previous.cart.length &&
      orderRef.current.stage !== 'menu' && previous.order.stage !== 'menu';
    setCart(previous.cart); setQuantity(sameItem ? quantity : previous.quantity);
    orderRef.current = previous.order; setOrder(previous.order); previous.restore?.();
  }
  const items = 'draft' in order ? [...cart, {...order.draft, quantity}].map(item => ({...item, serviceType: order.draft.serviceType})) : cart;
  function deferService() {
    if (order.stage !== 'service_type' || submittedRequest.current) return;
    setCart([...cart, {menu: order.menu, temperature: order.temperature,
      selectedOptions: order.selectedOptions, quantity, serviceType: 'DINE_IN'}]);
    setQuantity(1); dispatch({type: 'continue'});
  }
  function continueOrder(record = true) {
    if (order.stage !== 'review' || submittedRequest.current) return;
    if (record) checkpoint();
    setCart(items); setQuantity(1); dispatch({type: 'continue'}, false);
  }
  function changeQuantity(index: number, value: number) {
    if (order.stage !== 'review' || submittedRequest.current || value < 1 || value > 99) return;
    if (index === cart.length) setQuantity(value);
    else setCart(cart.map((item, i) => i === index ? {...item, quantity: value} : item));
  }
  function removeItem(index: number) {
    if (order.stage !== 'review' || submittedRequest.current || index < 0 || index > cart.length) return;
    if (index < cart.length) {
      setCart(cart.filter((_, itemIndex) => itemIndex !== index));
      return;
    }
    const previousItem = cart.at(-1);
    setCart(cart.slice(0, -1));
    setQuantity(previousItem?.quantity ?? 1);
    dispatch({ type: 'remove_current_item', previousItem });
  }
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
  return { order, dispatch, back, canBack, confirm, items, continueOrder, deferService, changeQuantity, removeItem, quantity, setQuantity, locked: !!submittedRequest.current };
}
