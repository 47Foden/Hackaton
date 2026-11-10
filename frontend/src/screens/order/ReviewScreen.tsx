import type { OrderDraft, OrderFailure } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

interface ReviewScreenProps {
  draft: OrderDraft;
  items?: OrderDraft[];
  locked?: boolean;
  onContinue?: () => void;
  onQuantity?: (index: number, value: number) => void;
  isMock: boolean;
  pending: boolean;
  error?: OrderFailure;
  onConfirm: () => void;
}
export function ReviewScreen({ draft, isMock, pending, error, onConfirm, items = [draft], locked, onContinue, onQuantity }: ReviewScreenProps) {
  const confirmLabel = error?.kind === 'uncertain' ? '같은 주문 다시 시도' : error ? '다시 시도' : '주문 확정';
  const total = items.reduce((sum, item) => sum + (item.menu.price + item.selectedOptions.reduce((s, c) => s + c.price_delta_krw, 0)) * (item.quantity ?? 1), 0);
  return (
    <section className="order-step" aria-label="최종 주문 확인" aria-busy={pending}>
      {items.map((item, index) => <div key={index}>
        <OrderSummary {...item} />
        <div className="quantity-control" aria-label={item.menu.name + ' 수량'}>
          <button disabled={pending || locked || (item.quantity ?? 1) <= 1} onClick={() => onQuantity?.(index, (item.quantity ?? 1) - 1)} aria-label={item.menu.name + ' 수량 줄이기'}>−</button>
          <span aria-live="polite">{item.quantity ?? 1}잔</span>
          <button disabled={pending || locked || (item.quantity ?? 1) >= 99} onClick={() => onQuantity?.(index, (item.quantity ?? 1) + 1)} aria-label={item.menu.name + ' 수량 늘리기'}>+</button>
        </div>
      </div>)}
      <p className="order-step__total">합계 <strong>{total.toLocaleString('ko-KR')}원</strong></p>
      {isMock && <p className="order-step__note">개발 모드예요. 실제 주문 접수와 결제는 진행되지 않아요.</p>}
      {error && <p role="alert" className="order-step__note">{error.message}</p>}
      <div className="cart-actions">
      <button className="primary-button order-step__confirm" disabled={pending || locked || items.length >= 20} onClick={onContinue}>계속 주문하기</button>
      <button type="button" className="primary-button order-step__confirm"
        disabled={pending || error?.kind === 'conflict'} onClick={onConfirm}>
        {pending ? '주문 처리 중…' : error?.kind === 'conflict' ? '요청 정보 확인 필요' : `${confirmLabel}${isMock ? ' (개발용)' : ''}`}
      </button>
      </div>
    </section>
  );
}
