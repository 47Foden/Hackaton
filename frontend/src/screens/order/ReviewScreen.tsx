import type { OrderDraft } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

interface ReviewScreenProps {
  draft: OrderDraft;
  isMock: boolean;
  pending: boolean;
  error?: { message: string; uncertain: boolean };
  onConfirm: () => void;
}
export function ReviewScreen({ draft, isMock, pending, error, onConfirm }: ReviewScreenProps) {
  return (
    <section className="order-step" aria-label="최종 주문 확인" aria-busy={pending}>
      <OrderSummary {...draft} />
      <p className="order-step__total">합계 <strong>{draft.menu.price.toLocaleString('ko-KR')}원</strong></p>
      {isMock && <p className="order-step__note">개발 모드예요. 실제 주문 접수와 결제는 진행되지 않아요.</p>}
      {error && <p role="alert" className="order-step__note">
        {error.message} {error.uncertain ? '접수 여부가 불명확해요. 재전송하지 말고 접수 여부를 확인해 주세요.' : '주문은 접수되지 않았어요. 메뉴를 다시 선택하거나 재시도해 주세요.'}
      </p>}
      <button type="button" className="primary-button order-step__confirm"
        disabled={pending || error?.uncertain} onClick={onConfirm}>
        {pending ? '주문 처리 중…' : error?.uncertain ? '접수 여부 확인 필요' : isMock ? '주문 확정 (개발용)' : '주문 확정'}
      </button>
    </section>
  );
}
