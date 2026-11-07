import { useState } from 'react';
import { KioskLayout } from '../components/layout/KioskLayout';
import { MicrophoneButton } from '../components/voice/MicrophoneButton';
import { MenuBoard, type MenuBoardView } from '../components/menu/MenuBoard';
import { kioskApi, isMockApi } from '../api';
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
};

export function OrderScreen({ onHome }: { onHome: () => void }) {
  const { order, dispatch, confirm } = useOrderFlow(kioskApi);
  const { state: catalog, reload } = useMenus(kioskApi);
  const [menuView, setMenuView] = useState<MenuBoardView>({ mode: 'simplified', enlarged: false });
  const guide = order.stage === 'complete'
    ? { title: isMockApi ? '개발용 주문 흐름을 완료했어요.' : '주문이 접수되었어요.',
      description: isMockApi ? '실제 주문 접수와 결제는 진행되지 않았어요.' : '주문번호를 확인해 주세요.' }
    : guidance[order.stage];

  return (
    <KioskLayout {...guide}
      voiceDescription="마이크를 통한 음성 주문과 추천은 준비 중이에요."
      status={isMockApi ? '개발용 화면 · 실제 주문은 저장되지 않아요.' : '메뉴와 주문 내용을 확인해 주세요.'}
      microphone={<MicrophoneButton disabled helpText="준비 중" />}
      onHome={order.stage === 'submitting' ? undefined : onHome}
    >
      {order.stage === 'menu' && catalog.status === 'loading' && <p role="status">메뉴를 불러오는 중이에요…</p>}
      {order.stage === 'menu' && catalog.status === 'error' && <div role="alert">
        <p>{catalog.message}</p><button type="button" className="outline-button" onClick={reload}>다시 불러오기</button>
      </div>}
      {order.stage === 'menu' && catalog.status === 'ready' && (catalog.menus.length === 0
        ? <p role="status">표시할 메뉴가 없어요.</p>
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
        isMock={isMockApi} pending={order.stage === 'submitting'}
        error={order.stage === 'review' ? order.error : undefined} onConfirm={confirm} />}
      {order.stage === 'complete' && <CompletionScreen draft={order.draft} result={order.result}
        isMock={isMockApi} onHome={onHome} />}
    </KioskLayout>
  );
}
