import { useState } from 'react';
import { KioskLayout } from '../components/layout/KioskLayout';
import { MenuBoard, type MenuBoardView } from '../components/menu/MenuBoard';
import { CatalogStatus } from '../components/menu/CatalogStatus';
import { kioskApi, isMockOrderApi } from '../api';
import { getOrderGuidance } from '../data/orderGuidance';
import { useMenus } from '../hooks/useMenus';
import { useOrderFlow } from '../hooks/useOrderFlow';
import type { OrderSelection } from '../state/order';
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
  const reviewError = order.stage === 'review' ? order.error : undefined;

  function applySelection(selection: OrderSelection) {
    if (selection.type !== 'select_menu') {
      dispatch(selection);
      return;
    }
    if (catalog.status !== 'ready') return;
    const menu = catalog.menus.find(item => item.id === selection.menuId);
    if (menu) dispatch({ type: 'select_menu', menu });
  }

  return (
    <KioskLayout {...guide}
      status={isMockOrderApi ? '개발용 화면 · 실제 주문은 저장되지 않아요.' : '메뉴와 주문 내용을 확인해 주세요.'}
      onHome={order.stage === 'submitting' ? undefined : onHome}
    >
      {order.stage === 'menu' && catalog.status === 'loading' && <CatalogStatus status="loading" />}
      {order.stage === 'menu' && catalog.status === 'error' && <CatalogStatus status="error" message={catalog.message} onReload={reload} />}
      {order.stage === 'menu' && catalog.status === 'ready' && (catalog.menus.length === 0
        ? <CatalogStatus status="empty" onReload={reload} />
        : <MenuBoard menus={catalog.menus} simplifiedMenus={catalog.menus.filter(menu => menu.featured)}
          selectedMenu={null} view={menuView} onViewChange={setMenuView}
          onSelect={menuId => applySelection({ type: 'select_menu', menuId })} />)}
      {order.stage === 'temperature' && <TemperatureScreen menu={order.menu}
        onSelect={temperature => applySelection({ type: 'set_temperature', temperature })} />}
      {order.stage === 'service_type' && <ServiceTypeScreen menu={order.menu} temperature={order.temperature}
        onSelect={serviceType => applySelection({ type: 'set_service_type', serviceType })} />}
      {(order.stage === 'review' || order.stage === 'submitting') && <ReviewScreen draft={order.draft}
        isMock={isMockOrderApi} pending={order.stage === 'submitting'}
        error={reviewError} onConfirm={confirm} />}
      {order.stage === 'complete' && <CompletionScreen draft={order.draft} result={order.result}
        isMock={isMockOrderApi} onHome={onHome} />}
    </KioskLayout>
  );
}
