import type { OrderResponse } from '../../api/contracts';
import type { OrderDraft } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

export function CompletionScreen({ draft, result, isMock, onHome }: {
  draft: OrderDraft; result: OrderResponse; isMock: boolean; onHome: () => void;
}) {
  const confirmedDraft = { ...draft, menu: { ...draft.menu, name: result.menu_name, price: result.total_price_krw },
    temperature: result.temperature, serviceType: result.service_type };
  return (
    <section className="order-step order-completion" aria-label={isMock ? '개발용 주문 완료' : '주문 완료'}>
      <span className="order-completion__badge">{isMock ? '개발용 미리보기' : '주문 접수 완료'}</span>
      <dl className="order-completion__number-group">
        <dt>{isMock ? '예시 주문번호' : '주문번호'}</dt>
        <dd className="order-completion__number">{result.order_number}</dd>
      </dl>
      {isMock && <p className="order-step__note">실제 발급 번호가 아니에요. 주문은 저장되거나 접수되지 않았어요.</p>}
      <OrderSummary {...confirmedDraft} />
      <button type="button" className="primary-button order-step__confirm" onClick={onHome}>처음으로 돌아가기</button>
    </section>
  );
}
