import { useRef, useState } from 'react';
import { KioskLayout } from '../components/layout/KioskLayout';
import { OrderMicrophone } from '../components/voice/OrderMicrophone';
import { useMenus } from '../hooks/useMenus';
import { useOrderFlow } from '../hooks/useOrderFlow';
import { useVoiceGuidance } from '../hooks/useVoiceGuidance';
import { browserVoiceGuidance as voice } from '../voice/browserVoiceGuidance';
import { kioskApi, isMockOrderApi } from '../api';
import type { Menu } from '../data/menuCatalog';
import { TemperatureScreen } from './order/TemperatureScreen';
import { ServiceTypeScreen } from './order/ServiceTypeScreen';
import { ReviewScreen } from './order/ReviewScreen';
import { CompletionScreen } from './order/CompletionScreen';
import { getOrderGuidance } from '../data/orderGuidance';
import './order/OrderFlow.css';

export function VoiceOrderScreen({ onHome }: { onHome: () => void }) {
  const { order, dispatch, confirm } = useOrderFlow(kioskApi);
  const { state: catalog, reload } = useMenus(kioskApi);
  const [selected, setSelected] = useState<Menu | null>(null);
  const [error, setError] = useState('');
  const revision = useRef(0);
  const stage = selected ? 'menu_confirmation' : order.stage;
  const guide = selected ? { title: selected.name, description: '이 메뉴로 주문하시겠습니까? 네라고 말씀하시거나 버튼을 눌러 주세요.' }
    : order.stage === 'menu' ? { title: '음성 주문', description: '아래 마이크 버튼을 누르시면 음성 주문이 가능합니다. 메뉴 이름을 말씀해 주세요.' }
    : order.stage === 'review' ? { title: '주문 내용을 확인해 주세요.', description: '주문 확정이라고 말씀하시거나 주문 확정 버튼을 눌러 주세요.' }
    : order.stage === 'complete' ? { title: '주문이 접수되었어요.', description: `주문번호는 ${order.result.order_number}번입니다.` }
    : getOrderGuidance(order, isMockOrderApi);
  useVoiceGuidance(`${guide.title} ${guide.description}`);
  const enabled = !['submitting', 'complete'].includes(stage) && !(order.stage === 'review' && order.error?.kind === 'conflict');
  function interrupt() { ++revision.current; voice.cancel(); setError(''); }
  function choose(menu: Menu) { interrupt(); setSelected(menu); }
  function accept() {
    interrupt();
    if (selected) dispatch({ type: 'select_menu', menu: selected });
    setSelected(null);
  }
  async function record(audio: Blob, signal: AbortSignal) {
    const id = ++revision.current;
    try {
      const body = new FormData();
      body.set('audio', audio, 'recording.webm'); body.set('stage', stage);
      if (order.stage === 'temperature' || order.stage === 'service_type') body.set('selected_menu_id', order.menu.id);
      const response = await fetch('/api/voice/interpret', { method: 'POST', body,
        signal: AbortSignal.any([signal, AbortSignal.timeout(40_000)]) });
      const data = await response.json();
      if (signal.aborted || id !== revision.current) return;
      if (!response.ok) throw new Error(data?.detail?.message ?? '음성을 처리하지 못했어요. 다시 시도해 주세요.');
      voice.cancel();
      const action = data.action;
      if (stage === 'menu_confirmation' && action?.type === 'confirm') { accept(); return; }
      if (stage === 'review' && action?.type === 'confirm') { interrupt(); await confirm(); return; }
      if (stage === 'menu' && action?.type === 'select_menu' && catalog.status === 'ready') {
        const menu = catalog.menus.find(m => m.id === action.menu_id && m.available);
        if (menu) { choose(menu); return; }
      }
      if (order.stage === 'temperature' && action?.type === 'set_temperature' && order.menu.temperatures.includes(action.temperature)) {
        interrupt(); dispatch({ type: 'set_temperature', temperature: action.temperature }); return;
      }
      if (order.stage === 'service_type' && action?.type === 'set_service_type' && ['DINE_IN', 'TAKEOUT'].includes(action.service_type)) {
        interrupt(); dispatch({ type: 'set_service_type', serviceType: action.service_type }); return;
      }
      throw new Error(action?.type === 'recommend' ? '추천은 준비 중이에요. 메뉴 이름을 말씀해 주세요.' : '입력을 이해하지 못했어요. 다시 말씀하시거나 화면에서 선택해 주세요.');
    } catch (failure) {
      if (signal.aborted || id !== revision.current) return;
      const message = failure instanceof Error ? failure.message : '음성 처리에 실패했어요.';
      setError(message); voice.cancel(); voice.speak(message); throw failure;
    }
  }
  return <KioskLayout {...guide} status={isMockOrderApi ? '개발용 주문입니다.' : '음성 또는 터치로 주문해 주세요.'}
    onHome={order.stage === 'submitting' ? undefined : () => { interrupt(); onHome(); }}
    microphone={<OrderMicrophone key={stage} disabledReason={enabled ? undefined : '현재 단계에서는 녹음할 수 없어요.'} onRecordingComplete={record} />}>
    {error && <p role="alert">{error}</p>}
    {selected && <section className="order-step"><img src={selected.imageUrl} alt={selected.name} style={{ maxWidth: 240 }} /><h2>{selected.name}</h2><p>{selected.price.toLocaleString('ko-KR')}원</p>
      <button className="primary-button" onClick={accept}>네, 이 메뉴로 주문</button>
      <button onClick={() => { interrupt(); setSelected(null); }}>다른 메뉴 선택</button></section>}
    {stage === 'menu' && (catalog.status === 'ready' ? <section aria-label="음성 주문 메뉴판">
      {catalog.menus.filter(m => m.available).map(menu => <button key={menu.id} onClick={() => choose(menu)}>{menu.name}</button>)}
    </section> : <p>{catalog.status === 'loading' ? '메뉴를 불러오는 중이에요.' : '메뉴를 불러오지 못했어요.'}<button onClick={() => { interrupt(); reload(); }}>다시 불러오기</button></p>)}
    {order.stage === 'temperature' && <TemperatureScreen menu={order.menu} onSelect={temperature => { interrupt(); dispatch({ type: 'set_temperature', temperature }); }} />}
    {order.stage === 'service_type' && <ServiceTypeScreen menu={order.menu} temperature={order.temperature} onSelect={serviceType => { interrupt(); dispatch({ type: 'set_service_type', serviceType }); }} />}
    {(order.stage === 'review' || order.stage === 'submitting') && <ReviewScreen draft={order.draft} isMock={isMockOrderApi} pending={order.stage === 'submitting'}
      error={order.stage === 'review' ? order.error : undefined} onConfirm={() => { interrupt(); void confirm(); }} />}
    {order.stage === 'complete' && <CompletionScreen draft={order.draft} result={order.result} isMock={isMockOrderApi} onHome={() => { interrupt(); onHome(); }} />}
  </KioskLayout>;
}
