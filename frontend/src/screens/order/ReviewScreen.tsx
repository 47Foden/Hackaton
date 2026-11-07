import type { OrderDraft } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

export function ReviewScreen({ draft, onConfirm }: { draft: OrderDraft; onConfirm: () => void }) {
  return (
    <section className="order-step" aria-label="최종 주문 확인">
      <OrderSummary {...draft} />
      <p className="order-step__total">합계 <strong>{draft.menu.price.toLocaleString('ko-KR')}원</strong></p>
      <p className="order-step__note">화면 흐름을 확인하는 개발 모드예요. 실제 주문 접수와 결제는 진행되지 않아요.</p>
      <button type="button" className="primary-button order-step__confirm" onClick={onConfirm}>주문 확정 (개발용)</button>
    </section>
  );
}
