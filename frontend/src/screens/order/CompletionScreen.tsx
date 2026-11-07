import type { OrderDraft } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

export function CompletionScreen({ draft, onHome }: { draft: OrderDraft; onHome: () => void }) {
  return (
    <section className="order-step order-completion" aria-label="개발용 주문 완료">
      <span className="order-completion__badge">개발용 미리보기</span>
      <p>예시 주문번호</p>
      <p className="order-completion__number">DEV-DEMO</p>
      <p className="order-step__note">실제 발급 번호가 아니에요. 주문은 저장되거나 접수되지 않았어요.</p>
      <OrderSummary {...draft} />
      <button type="button" className="primary-button order-step__confirm" onClick={onHome}>처음으로 돌아가기</button>
    </section>
  );
}
