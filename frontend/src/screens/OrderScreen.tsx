import { useReducer, useState } from 'react';
import { KioskLayout } from '../components/layout/KioskLayout';
import { MicrophoneButton } from '../components/voice/MicrophoneButton';
import { MenuBoard, type MenuBoardView } from '../components/menu/MenuBoard';
import { menuCatalog, simplifiedMenuCatalog } from '../data/menuCatalog';
import { initialOrderState, orderReducer } from '../state/order';
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
  complete: { title: '개발용 주문 흐름을 완료했어요.', description: '실제 주문 접수와 결제는 진행되지 않았어요.' },
};

export function OrderScreen({ onHome }: { onHome: () => void }) {
  const [order, dispatch] = useReducer(orderReducer, initialOrderState);
  const [menuView, setMenuView] = useState<MenuBoardView>({ mode: 'simplified', enlarged: false });
  const guide = guidance[order.stage];

  return (
    <KioskLayout
      {...guide}
      voiceDescription="마이크를 통한 음성 주문과 추천은 준비 중이에요."
      status={order.stage === 'menu' ? '원하는 메뉴를 선택해 주세요.' : '개발용 화면 · 실제 주문은 저장되지 않아요.'}
      microphone={<MicrophoneButton disabled helpText="준비 중" />}
      onHome={onHome}
    >
      {order.stage === 'menu' && <MenuBoard
        menus={menuCatalog}
        simplifiedMenus={simplifiedMenuCatalog}
        selectedMenu={null}
        view={menuView}
        onViewChange={setMenuView}
        onSelect={name => {
          const menu = menuCatalog.find(item => item.name === name);
          if (menu) dispatch({ type: 'select_menu', menu });
        }}
      />}
      {order.stage === 'temperature' && <TemperatureScreen menu={order.menu}
        onSelect={temperature => dispatch({ type: 'set_temperature', temperature })} />}
      {order.stage === 'service_type' && <ServiceTypeScreen menu={order.menu} temperature={order.temperature}
        onSelect={serviceType => dispatch({ type: 'set_service_type', serviceType })} />}
      {order.stage === 'review' && <ReviewScreen draft={order.draft}
        onConfirm={() => dispatch({ type: 'confirm' })} />}
      {order.stage === 'complete' && <CompletionScreen draft={order.draft} onHome={onHome} />}
    </KioskLayout>
  );
}
