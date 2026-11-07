import { useState } from 'react';
import { KioskLayout } from '../components/layout/KioskLayout';
import { MicrophoneButton } from '../components/voice/MicrophoneButton';
import { MenuBoard, type MenuBoardView } from '../components/menu/MenuBoard';
import { CatalogStatus } from '../components/menu/CatalogStatus';
import { kioskApi, isMockOrderApi } from '../api';
import { getOrderGuidance } from '../data/orderGuidance';
import { useMenus } from '../hooks/useMenus';
import { useOrderFlow } from '../hooks/useOrderFlow';
import { useVoiceGuidance } from '../hooks/useVoiceGuidance';
import { TemperatureScreen } from './order/TemperatureScreen';
import { ServiceTypeScreen } from './order/ServiceTypeScreen';
import { ReviewScreen } from './order/ReviewScreen';
import { CompletionScreen } from './order/CompletionScreen';
import './order/OrderFlow.css';

export function OrderScreen({ onHome }: { onHome: () => void }) {
  const { order, dispatch, confirm } = useOrderFlow(kioskApi);
  const { state: catalog, reload } = useMenus(kioskApi);
  const [menuView, setMenuView] = useState<MenuBoardView>({ mode: 'simplified', enlarged: false });

  const guide = getOrderGuidance(order, isMockOrderApi);
  useVoiceGuidance(`${guide.title} ${guide.description}`);
  const reviewError = order.stage === 'review' ? order.error : undefined;

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
