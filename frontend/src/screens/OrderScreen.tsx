import { useEffect, useState } from 'react';
import { KioskLayout } from '../components/layout/KioskLayout';
import { MicrophoneButton } from '../components/voice/MicrophoneButton';
import { MenuBoard, type MenuBoardView } from '../components/menu/MenuBoard';
import { CatalogStatus } from '../components/menu/CatalogStatus';
import { kioskApi, isMockOrderApi } from '../api';
import { useMenus } from '../hooks/useMenus';
import { useOrderFlow } from '../hooks/useOrderFlow';
import { TemperatureScreen } from './order/TemperatureScreen';
import { ServiceTypeScreen } from './order/ServiceTypeScreen';
import { ReviewScreen } from './order/ReviewScreen';
import { CompletionScreen } from './order/CompletionScreen';
import './order/OrderFlow.css';

const guidance = {
  menu: { title: '어떤 음료를 드시겠어요?', description: '메뉴를 눌러 선택해 주세요.' },
  temperature: { title: '따뜻하게, 차갑게?', description: '원하는 음료 온도를 선택해 주세요.' },
  service_type: { title: '어디에서 드시겠어요?', description: '매장 또는 포장을 선택해 주세요.' },
  review: { title: '주문 내용을 확인해 주세요.', description: '메뉴와 옵션을 확인한 후 주문 확정을 눌러 주세요.' },
  submitting: { title: '주문을 처리하고 있어요.', description: '잠시만 기다려 주세요.' },
  rejected: { title: '주문이 접수되지 않았어요.', description: '다시 시도하거나 처음으로 돌아가 메뉴를 다시 선택해 주세요.' },
  uncertain: { title: '주문 접수 여부를 확인해 주세요.', description: '이미 접수됐을 수 있어요. 새 주문을 넣기 전에 직원에게 확인해 주세요.' },
};

export function OrderScreen({ onHome }: { onHome: () => void }) {
  const { order, dispatch, confirm } = useOrderFlow(kioskApi);
  const { state: catalog, reload } = useMenus(kioskApi);
  const [menuView, setMenuView] = useState<MenuBoardView>({ mode: 'simplified', enlarged: false });

  useEffect(() => () => window.speechSynthesis?.cancel(), []);

  const reviewError = order.stage === 'review' ? order.error : undefined;
  const guide = order.stage === 'complete'
    ? { title: isMockOrderApi ? '개발용 주문 흐름을 완료했어요.' : '주문이 접수되었어요.',
      description: isMockOrderApi ? '실제 주문 접수와 결제는 진행되지 않았어요.' : '주문번호를 확인해 주세요.' }
    : guidance[reviewError ? (reviewError.uncertain ? 'uncertain' : 'rejected') : order.stage];

  return (
    <KioskLayout {...guide}
      voiceDescription="마이크를 통한 음성 주문과 추천은 준비 중이에요."
      status={isMockOrderApi ? '개발용 화면 · 실제 주문은 저장되지 않아요.' : '메뉴와 주문 내용을 확인해 주세요.'}
      microphone={<MicrophoneButton disabled helpText="준비 중" />}
      onHome={order.stage === 'submitting' ? undefined : onHome}
    >
      {order.stage === 'menu' && catalog.status === 'loading' && <CatalogStatus status="loading" />}
      {order.stage === 'menu' && catalog.status === 'error' && <CatalogStatus status="error" message={catalog.message} onReload={reload} />}
      {order.stage === 'menu' && catalog.status === 'ready' && (catalog.menus.length === 0
        ? <CatalogStatus status="empty" onReload={reload} />
        : <MenuBoard menus={catalog.menus} simplifiedMenus={catalog.menus.filter(menu => menu.featured)}
          selectedMenu={null} view={menuView} onViewChange={setMenuView}
          onSelect={name => {
            const menu = catalog.menus.find(item => item.name === name);
            if (menu) dispatch({ type: 'select_menu', menu });
          }} />)}
      {order.stage === 'temperature' && <TemperatureScreen menu={order.menu}
        onSelect={temperature => dispatch({ type: 'set_temperature', temperature })} />}
      {order.stage === 'service_type' && <ServiceTypeScreen menu={order.menu} temperature={order.temperature}
        onSelect={serviceType => dispatch({ type: 'set_service_type', serviceType })} />}
      {(order.stage === 'review' || order.stage === 'submitting') && <ReviewScreen draft={order.draft}
        isMock={isMockOrderApi} pending={order.stage === 'submitting'}
        error={reviewError} onConfirm={confirm} />}
      {order.stage === 'complete' && <CompletionScreen draft={order.draft} result={order.result}
        isMock={isMockOrderApi} onHome={onHome} />}
    </KioskLayout>
  );
}
