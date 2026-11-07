import type { OrderDraft, OrderFailure } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

interface ReviewScreenProps {
  draft: OrderDraft;
  isMock: boolean;
  pending: boolean;
  error?: OrderFailure;
  onConfirm: () => void;
}
export function ReviewScreen({ draft, isMock, pending, error, onConfirm }: ReviewScreenProps) {
  const confirmLabel = error?.kind === 'uncertain' ? '같은 주문 다시 시도' : error ? '다시 시도' : '주문 확정';
  return (
    <section className="order-step" aria-label="최종 주문 확인" aria-busy={pending}>
      <OrderSummary {...draft} />
      <p className="order-step__total">합계 <strong>{draft.menu.price.toLocaleString('ko-KR')}원</strong></p>
      {isMock && <p className="order-step__note">개발 모드예요. 실제 주문 접수와 결제는 진행되지 않아요.</p>}
      {error && <p role="alert" className="order-step__note">{error.message}</p>}
      <button type="button" className="primary-button order-step__confirm"
        disabled={pending || error?.kind === 'conflict'} onClick={onConfirm}>
        {pending ? '주문 처리 중…' : error?.kind === 'conflict' ? '요청 정보 확인 필요' : `${confirmLabel}${isMock ? ' (개발용)' : ''}`}
      </button>
    </section>
  );
}
