import type { OrderState } from '../state/order';

const guidance = {
  menu: { title: '어떤 음료를 드시겠어요?', description: '메뉴를 눌러 선택해 주세요.' },
  temperature: { title: '따뜻하게, 차갑게?', description: '원하는 음료 온도를 선택해 주세요.' },
  service_type: { title: '어디에서 드시겠어요?', description: '매장 또는 포장을 선택해 주세요.' },
  review: { title: '주문 내용을 확인해 주세요.', description: '메뉴와 옵션을 확인한 후 주문 확정을 눌러 주세요.' },
  submitting: { title: '주문을 처리하고 있어요.', description: '잠시만 기다려 주세요.' },
  rejected: { title: '주문이 접수되지 않았어요.', description: '다시 시도하거나 처음으로 돌아가 메뉴를 다시 선택해 주세요.' },
  uncertain: { title: '주문 접수 여부를 확인해 주세요.', description: '같은 주문으로 다시 시도하면 접수 결과를 확인할 수 있어요.' },
  conflict: { title: '주문 요청을 확인해 주세요.', description: '직원에게 기존 주문의 접수 내역을 확인해 주세요.' },
  complete: { title: '주문이 접수되었어요.', description: '주문번호를 확인해 주세요.' },
  mockComplete: { title: '개발용 주문 흐름을 완료했어요.', description: '실제 주문 접수와 결제는 진행되지 않았어요.' },
};

export function getOrderGuidance(order: OrderState, isMock: boolean) {
  if (order.stage === 'complete' && isMock) return guidance.mockComplete;
  if (order.stage === 'review' && order.error) return guidance[order.error.kind];
  return guidance[order.stage];
}
