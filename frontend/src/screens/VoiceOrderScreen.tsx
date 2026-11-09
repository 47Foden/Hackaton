import { useRef, useState } from 'react';
import { KioskLayout } from '../components/layout/KioskLayout';
import { MenuBoard, type MenuBoardView } from '../components/menu/MenuBoard';
import { CatalogStatus } from '../components/menu/CatalogStatus';
import { MenuImage } from '../components/menu/MenuImage';
import { OrderMicrophone } from '../components/voice/OrderMicrophone';
import { useMenus } from '../hooks/useMenus';
import { useOrderFlow } from '../hooks/useOrderFlow';
import { useVoiceGuidance } from '../hooks/useVoiceGuidance';
import { browserVoiceGuidance as voice } from '../voice/browserVoiceGuidance';
import { kioskApi, isMockOrderApi } from '../api';
import type { Menu } from '../data/menuCatalog';
import { TemperatureScreen } from './order/TemperatureScreen';
import { CustomizationScreen } from './order/CustomizationScreen';
import { ServiceTypeScreen } from './order/ServiceTypeScreen';
import { ReviewScreen } from './order/ReviewScreen';
import { CompletionScreen } from './order/CompletionScreen';
import { getOrderGuidance } from '../data/orderGuidance';
import './order/OrderFlow.css';

export function VoiceOrderScreen({ onHome }: { onHome: () => void }) {
  const { order, dispatch, confirm } = useOrderFlow(kioskApi);
  const { state: catalog, reload } = useMenus(kioskApi);
  const [candidates, setCandidates] = useState<string[] | null>(null);
  const [selected, setSelected] = useState<Menu | null>(null);
  const [menuView, setMenuView] = useState<MenuBoardView>({ enlarged: false });
  const [error, setError] = useState('');
  const [transcript, setTranscript] = useState('');
  const [recommendationNotice, setRecommendationNotice] = useState('');
  const [directCandidates, setDirectCandidates] = useState<{ menu_id: string; temperature: string; reason: string }[]>([]);
  const revision = useRef(0);
  const stage = selected ? 'menu_confirmation' : order.stage === 'menu' && candidates?.length ? 'recommendations' : order.stage;
  const guide = selected ? { title: selected.name, description: '이 메뉴로 주문하시겠습니까? 네라고 말씀하시거나 버튼을 눌러 주세요.' }
    : candidates !== null && order.stage === 'menu' ? { title: candidates.length ? '추천 메뉴' : '조건에 맞는 메뉴가 없어요.', description: '추천 메뉴를 확인해 주세요. 재추천을 원하시면 다시 추천이라고 말씀하시거나 버튼을 누르면 초기 음성 입력 화면으로 돌아갑니다.' }
    : order.stage === 'menu' ? { title: '음성 주문', description: '아래 마이크 버튼을 누르시면 음성 주문이 가능합니다. 메뉴 이름이나 원하는 맛과 음료 종류를 말씀해 주세요.' }
    : order.stage === 'review' ? { title: '주문 내용을 확인해 주세요.', description: '주문 확정이라고 말씀하시거나 주문 확정 버튼을 눌러 주세요.' }
    : order.stage === 'complete' ? { title: '주문이 접수되었어요.', description: `주문번호는 ${order.result.order_number}번입니다.` }
    : getOrderGuidance(order, isMockOrderApi);
  useVoiceGuidance(`${guide.title} ${guide.description}`);
  const enabled = !['customization', 'submitting', 'complete'].includes(stage) && !(order.stage === 'review' && order.error?.kind === 'conflict');
  function interrupt() { ++revision.current; voice.cancel(); setError(''); }
  function choose(menu: Menu) { interrupt(); setSelected(menu); }
  function accept() {
    interrupt();
    if (selected) dispatch({ type: 'select_menu', menu: selected });
    setSelected(null);
    setCandidates(null);
  }
  async function record(audio: Blob, signal: AbortSignal) {
    const id = ++revision.current;
    setTranscript('');
    setError('');
    setRecommendationNotice(''); setDirectCandidates([]);
    try {
      const body = new FormData();
      body.set('audio', audio, 'recording.webm'); body.set('stage', stage);
      if (stage === 'recommendations') candidates?.forEach(menuId => body.append('candidate_menu_ids', menuId));
      if (order.stage === 'temperature' || order.stage === 'service_type') body.set('selected_menu_id', order.menu.id);
      const response = await fetch('/api/voice/interpret', { method: 'POST', body,
        signal: AbortSignal.any([signal, AbortSignal.timeout(140_000)]) });
      const data = await response.json();
      if (signal.aborted || id !== revision.current) return;
      if (!response.ok) throw new Error(`${data?.detail?.message ?? '음성을 처리하지 못했어요. 다시 시도해 주세요.'}${data?.detail?.code ? ` (${data.detail.code})` : ''}`);
      setTranscript(typeof data.transcript === 'string' ? data.transcript : '');
      voice.cancel();
      const action = data.action;
      if (['menu', 'recommendations'].includes(stage) && action?.type === 'direct_recommendation' && catalog.status === 'ready') {
        if (action.status === 'recommend') {
          const recs = action.recommendations;
          if (!Array.isArray(recs) || recs.length !== 1 || !recs.every(r =>
            catalog.menus.some(m => m.id === r.menu_id && m.available && m.temperatures.includes(r.temperature)))) throw new Error('LLM 추천 결과를 확인하지 못했어요.');
          interrupt(); setCandidates(recs.map(r => r.menu_id)); setDirectCandidates(recs); return;
        }
        if (!['clarify', 'insufficient_data'].includes(action.status)) throw new Error('LLM 응답을 확인하지 못했어요.');
        const messages = action.status === 'clarify' ? action.questions : action.missing_information;
        if (!Array.isArray(messages) || !messages.length || !messages.every(m => typeof m === 'string')) throw new Error('LLM 안내를 확인하지 못했어요.');
        const message = messages.join(' ');
        interrupt(); setCandidates(null); setRecommendationNotice(message); voice.speak(message); return;
      }
      if (stage === 'menu_confirmation' && action?.type === 'confirm') { accept(); return; }
      if (stage === 'review' && action?.type === 'confirm') { interrupt(); await confirm(); return; }
      if (['menu', 'recommendations'].includes(stage) && action?.type === 'restart_recommendation') { interrupt(); setCandidates(null); setTranscript(''); return; }
      if (['menu', 'recommendations'].includes(stage) && action?.type === 'recommendation_results' && catalog.status === 'ready') {
        const ids = action.menu_ids;
        if (!Array.isArray(ids) || ids.length > 4 || new Set(ids).size !== ids.length || !ids.every(id => catalog.menus.some(m => m.id === id && m.available))) throw new Error('추천 결과를 확인하지 못했어요.');
        interrupt(); setCandidates(ids); return;
      }
      if (['menu', 'recommendations'].includes(stage) && action?.type === 'select_menu' && catalog.status === 'ready') {
        const menu = catalog.menus.find(m => m.id === action.menu_id && m.available && (stage !== 'recommendations' || candidates?.includes(m.id)));
        if (menu) { choose(menu); return; }
      }
      if (order.stage === 'temperature' && action?.type === 'set_temperature' && order.menu.temperatures.includes(action.temperature)) {
        interrupt(); dispatch({ type: 'set_temperature', temperature: action.temperature }); return;
      }
      if (order.stage === 'service_type' && action?.type === 'set_service_type' && ['DINE_IN', 'TAKEOUT'].includes(action.service_type)) {
        interrupt(); dispatch({ type: 'set_service_type', serviceType: action.service_type }); return;
      }
      throw new Error(action?.type === 'recommend' ? '추천은 준비 중이에요. 메뉴 이름이나 원하는 맛과 음료 종류를 말씀해 주세요.' : '입력을 이해하지 못했어요. 다시 말씀하시거나 화면에서 선택해 주세요.');
    } catch (failure) {
      if (signal.aborted || id !== revision.current) return;
      const message = failure instanceof Error ? failure.message : '음성 처리에 실패했어요.';
      setError(message); voice.cancel(); voice.speak(message); throw failure;
    }
  }
  return <KioskLayout {...guide} status={isMockOrderApi ? '개발용 주문입니다.' : '음성 또는 터치로 주문해 주세요.'}
    onHome={order.stage === 'submitting' ? undefined : () => { interrupt(); onHome(); }}
    microphone={<OrderMicrophone key={stage} disabledReason={enabled ? undefined : '현재 단계에서는 녹음할 수 없어요.'} onRecordingComplete={record} />}>
    {enabled && <p className="order-step__note">마이크를 누르고 말씀하신 뒤 ‘녹음 종료’를 눌러 주세요. 종료 후 음성을 분석합니다.</p>}
    {transcript && <p role="status" className="order-step__note">인식한 말: {transcript}</p>}
    {error && <p role="alert">{error}</p>}
    {recommendationNotice && !selected && order.stage === 'menu' && <section aria-label="추천 추가 안내"><p role="status">{recommendationNotice}</p>
      <p>대화 기록은 아직 이어지지 않습니다. 원래 조건과 답을 합쳐 다시 말씀해 주세요.</p></section>}
    {selected && <section className="voice-menu-confirmation" aria-label="선택 메뉴 확인">
      <div className="voice-menu-confirmation__card">
        <MenuImage src={selected.imageUrl} className="voice-menu-confirmation__image" />
        <h2>{selected.name}</h2><p>{selected.price.toLocaleString('ko-KR')}원</p>
      </div>
      <div className="voice-menu-confirmation__actions">
        <button className="primary-button" onClick={accept}>네, 이 메뉴로 주문</button>
        <button className="primary-button" onClick={() => { interrupt(); setSelected(null); }}>다른 메뉴 선택</button>
      </div>
    </section>}
    {candidates !== null && !selected && order.stage === 'menu' && <section aria-label="추천 결과">
      {directCandidates.map(candidate => <p key={candidate.menu_id} className="order-step__note">
        LLM 추천 · {candidate.temperature}: {candidate.reason}
      </p>)}
      {catalog.status === 'ready' && candidates.length > 0 && <MenuBoard menus={candidates.flatMap(id => catalog.menus.filter(m => m.id === id))} selectedMenu={null} view={menuView} onViewChange={view => { interrupt(); setMenuView(view); }} onSelect={id => { const menu = catalog.menus.find(m => m.id === id && m.available); if(menu) choose(menu); }} />}
      <button className="primary-button" onClick={() => { interrupt(); setCandidates(null); setTranscript(''); setDirectCandidates([]); setRecommendationNotice(''); }}>다시 추천받기</button>
    </section>}
    {stage === 'menu' && candidates === null && (catalog.status === 'ready'
      ? catalog.menus.length === 0 ? <CatalogStatus status="empty" onReload={reload} />
        : <MenuBoard groupByCategory menus={catalog.menus} selectedMenu={null}
          view={menuView} onViewChange={view => { interrupt(); setMenuView(view); }}
          onSelect={menuId => { const menu = catalog.menus.find(m => m.id === menuId && m.available); if (menu) choose(menu); }} />
      : catalog.status === 'loading' ? <CatalogStatus status="loading" />
        : <CatalogStatus status="error" message={catalog.message} onReload={() => { interrupt(); reload(); }} />)}
    {order.stage === 'temperature' && <TemperatureScreen menu={order.menu} onSelect={temperature => { interrupt(); dispatch({ type: 'set_temperature', temperature }); }} />}
    {order.stage === 'customization' && <CustomizationScreen menu={order.menu} temperature={order.temperature}
      onContinue={ids => { interrupt(); dispatch({ type: 'set_options', ids }); }} />}
    {order.stage === 'service_type' && <ServiceTypeScreen menu={order.menu} temperature={order.temperature} selectedOptions={order.selectedOptions}
      onSelect={serviceType => { interrupt(); dispatch({ type: 'set_service_type', serviceType }); }} />}
    {(order.stage === 'review' || order.stage === 'submitting') && <ReviewScreen draft={order.draft} isMock={isMockOrderApi} pending={order.stage === 'submitting'}
      error={order.stage === 'review' ? order.error : undefined} onConfirm={() => { interrupt(); void confirm(); }} />}
    {order.stage === 'complete' && <CompletionScreen draft={order.draft} result={order.result} isMock={isMockOrderApi} onHome={() => { interrupt(); onHome(); }} />}
  </KioskLayout>;
}
