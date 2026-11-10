import { useEffect, useRef, useState } from 'react';
import { mergeVoiceOptions, readVoiceOptions, selectedCustomization, validateVoiceOptions } from '../state/voiceOptions';
import type { VoiceOptions } from '../state/voiceOptions';
import { KioskLayout } from '../components/layout/KioskLayout';
import { MenuBoard, type MenuBoardView } from '../components/menu/MenuBoard';
import { CatalogStatus } from '../components/menu/CatalogStatus';
import { MenuImage } from '../components/menu/MenuImage';
import { OrderMicrophone } from '../components/voice/OrderMicrophone';
import { VoiceIntentMicrophone, type VoiceIntent } from '../components/voice/VoiceIntentMicrophone';
import { useMenus } from '../hooks/useMenus';
import { useOrderFlow } from '../hooks/useOrderFlow';
import { useVoiceGuidance } from '../hooks/useVoiceGuidance';
import { browserVoiceGuidance as voice } from '../voice/browserVoiceGuidance';
import { acceptsVoiceAction, voiceRetryMessage } from '../voice/voiceIntent';
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
  const revision = useRef(0);
  const pending = useRef<AbortController | null>(null);
  const sessionRef = useRef<VoiceOptions>({});
  const [session, setSession] = useState<VoiceOptions>({});
  useEffect(() => () => { ++revision.current; pending.current?.abort(); }, []);
  function save(options: VoiceOptions) { sessionRef.current = options; setSession(options); return options; }
  const contextMenu = selected ?? ('menu' in order ? order.menu : undefined);
  const contextTemperature = 'temperature' in order ? order.temperature : session.temperature;
  const validated = contextMenu ? validateVoiceOptions(session, contextMenu, contextTemperature) : session;
  const optionNotice = validated.unresolved_fields?.length || validated.customization?.status === 'needs_clarification'
    ? '말씀하신 옵션 중 확인이 필요한 항목이 있어요. 가능한 선택은 유지했으니 화면에서 확인해 주세요.' : '';
  const stage = selected ? 'menu_confirmation' : order.stage === 'menu' && candidates?.length ? 'recommendations' : order.stage;
  const guide = selected ? { title: selected.name, description: '이 메뉴로 주문하시겠습니까? 네라고 말씀하시거나 버튼을 눌러 주세요.' }
    : candidates !== null && order.stage === 'menu' ? { title: candidates.length ? '추천 메뉴' : '조건에 맞는 메뉴가 없어요.', description: '추천 메뉴를 터치하거나 주문하기를 눌러 선택해 주세요. 새 조건으로 추천받으려면 메뉴 추천받기를 눌러 주세요. 다시 추천받기는 초기 화면으로 돌아갑니다.' }
    : order.stage === 'menu' ? { title: '음성 주문', description: '메뉴를 정하셨다면 주문하기를, 추천이 필요하면 메뉴 추천받기를 눌러 말씀해 주세요.' }
    : order.stage === 'review' ? { title: '주문 내용을 확인해 주세요.', description: '주문 확정이라고 말씀하시거나 주문 확정 버튼을 눌러 주세요.' }
    : order.stage === 'complete' ? { title: '주문이 접수되었어요.', description: `주문번호는 ${order.result.order_number}번입니다.` }
    : getOrderGuidance(order, isMockOrderApi);
  useVoiceGuidance(`${guide.title} ${guide.description}`);
  const enabled = !['submitting', 'complete'].includes(stage) && !(order.stage === 'review' && order.error?.kind === 'conflict');
  function interrupt() { ++revision.current; pending.current?.abort(); voice.cancel(); setError(''); }
  function restart() { interrupt(); save({}); setSelected(null); setCandidates(null); setTranscript(''); }
  function home() { interrupt(); save({}); onHome(); }
  function choose(menu: Menu, options = sessionRef.current) { interrupt(); save(options); setSelected(menu); }
  function accept(options = sessionRef.current) {
    interrupt();
    save(options);
    if (selected) dispatch({ type: 'select_menu', menu: selected, voiceOptions: options });
    setSelected(null);
    setCandidates(null);
  }
  async function record(audio: Blob, signal: AbortSignal, intent?: VoiceIntent) {
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    const id = ++revision.current;
    setTranscript('');
    setError('');
    try {
      const body = new FormData();
      body.set('audio', audio, 'recording.webm'); body.set('stage', stage);
      if (intent) body.set('intent', intent);
      if (stage === 'recommendations') candidates?.forEach(menuId => body.append('candidate_menu_ids', menuId));
      if (contextMenu && ['menu_confirmation', 'temperature', 'customization', 'service_type'].includes(stage)) {
        body.set('selected_menu_id', contextMenu.id);
        const temperature = contextTemperature ?? (contextMenu.temperatures.length === 1 ? contextMenu.temperatures[0] : undefined);
        if (temperature && contextMenu.temperatures.includes(temperature)) body.set('selected_temperature', temperature);
      }
      const response = await fetch('/api/voice/interpret', { method: 'POST', body,
        signal: AbortSignal.any([signal, controller.signal, AbortSignal.timeout(140_000)]) });
      const data = await response.json();
      if (signal.aborted || controller.signal.aborted || id !== revision.current) return;
      if (!response.ok) throw new Error(`${data?.detail?.message ?? '음성을 처리하지 못했어요. 다시 시도해 주세요.'}${data?.detail?.code ? ` (${data.detail.code})` : ''}`);
      setTranscript(typeof data.transcript === 'string' ? data.transcript : '');
      voice.cancel();
      const action = data.action;
      if (intent && !acceptsVoiceAction(intent, action?.type)) {
        throw new Error('선택한 입력 목적에 맞는 응답을 받지 못했어요. 같은 버튼을 눌러 다시 말씀해 주세요.');
      }
      const incoming = readVoiceOptions(data.recognized_options);
      const options = mergeVoiceOptions(intent === 'recommend' ? {} : sessionRef.current, incoming);
      if (['menu', 'recommendations'].includes(stage) && action?.type === 'direct_recommendation' && catalog.status === 'ready') {
        if (action.status === 'recommend') {
          const recs = action.recommendations;
          if (!Array.isArray(recs) || recs.length === 0 || recs.length > catalog.menus.length
            || !recs.every(r => r && catalog.menus.some(m => m.id === r.menu_id && m.available
              && m.temperatures.includes(r.temperature) && (!options.temperature || r.temperature === options.temperature)))
            || new Set(recs.map(r => r.menu_id)).size !== recs.length) throw new Error('LLM 추천 결과를 확인하지 못했어요.');
          interrupt(); save(options); setCandidates(recs.map(r => r.menu_id)); return;
        }
        if (action.status !== 'insufficient_data' || !Array.isArray(action.recommendations)
          || action.recommendations.length !== 0) throw new Error('LLM 응답을 확인하지 못했어요.');
        interrupt(); save(options); setCandidates([]); return;
      }
      if (stage === 'menu_confirmation' && action?.type === 'confirm') { accept(options); return; }
      if (stage === 'review' && action?.type === 'confirm') { interrupt(); await confirm(); return; }
      if (['menu', 'recommendations'].includes(stage) && action?.type === 'restart_recommendation') { restart(); return; }
      if (['menu', 'recommendations'].includes(stage) && action?.type === 'select_menu' && catalog.status === 'ready') {
        const menu = catalog.menus.find(m => m.id === action.menu_id && m.available && (stage !== 'recommendations' || candidates?.includes(m.id)));
        if (menu) { choose(menu, options); return; }
      }
      if (order.stage === 'temperature' && action?.type === 'set_temperature' && order.menu.temperatures.includes(action.temperature)) {
        interrupt();
        const next = save(mergeVoiceOptions(options, { temperature: action.temperature }));
        dispatch({ type: 'set_temperature', temperature: action.temperature, voiceOptions: next }); return;
      }
      if (order.stage === 'customization' && action?.type === 'set_options' && incoming?.customization) {
        interrupt(); save(options);
        dispatch({ type: 'apply_voice_options', voiceOptions: options });
        return;
      }
      if (order.stage === 'service_type' && action?.type === 'set_service_type' && ['DINE_IN', 'TAKEOUT'].includes(action.service_type)) {
        interrupt();
        const next = save(mergeVoiceOptions(options, { service_type: action.service_type }));
        dispatch({ type: 'apply_voice_options', voiceOptions: next }); return;
      }
      // A failed new recommendation must not invalidate the current session.
      if (intent !== 'recommend' && action?.type === 'retry' && incoming?.unresolved_fields?.length) {
        save(mergeVoiceOptions(sessionRef.current, { unresolved_fields: incoming.unresolved_fields }));
      }
      throw new Error(voiceRetryMessage(intent, action?.reason));
    } catch (failure) {
      if (signal.aborted || controller.signal.aborted || id !== revision.current) return;
      const message = failure instanceof Error ? failure.message : '음성 처리에 실패했어요.';
      setError(message); voice.cancel(); voice.speak(message); throw failure;
    } finally {
      if (pending.current === controller) pending.current = null;
    }
  }
  return <KioskLayout {...guide} status={isMockOrderApi ? '개발용 주문입니다.' : undefined}
    onHome={order.stage === 'submitting' ? undefined : home}
    microphone={['menu', 'recommendations'].includes(stage)
      ? <VoiceIntentMicrophone key={stage} onRecordingComplete={record} />
      : <OrderMicrophone key={stage} disabledReason={enabled ? undefined : '현재 단계에서는 녹음할 수 없어요.'} onRecordingComplete={record} />}>
    {enabled && <p className="order-step__note">{['menu', 'recommendations'].includes(stage)
      ? '주문하기 또는 메뉴 추천받기를 누르고 말씀하신 뒤 ‘녹음 종료’를 눌러 주세요. 종료 후 음성을 분석합니다.'
      : '마이크를 누르고 말씀하신 뒤 ‘녹음 종료’를 눌러 주세요. 종료 후 음성을 분석합니다.'}</p>}
    {transcript && <p role="status" className="order-step__note">인식한 말: {transcript}</p>}
    {error && <p role="alert">{error}</p>}
    {optionNotice && <p role="status">{optionNotice}</p>}
    {selected && <section className="voice-menu-confirmation" aria-label="선택 메뉴 확인">
      <div className="voice-menu-confirmation__card">
        <MenuImage src={selected.imageUrl} className="voice-menu-confirmation__image" />
        <h2>{selected.name}</h2><p>{selected.price.toLocaleString('ko-KR')}원</p>
      </div>
      <div className="voice-menu-confirmation__actions">
        <button className="primary-button" onClick={() => accept()}>네, 이 메뉴로 주문</button>
        <button className="primary-button" onClick={() => { interrupt(); setSelected(null); }}>다른 메뉴 선택</button>
      </div>
    </section>}
    {candidates !== null && !selected && order.stage === 'menu' && <section aria-label="추천 결과">
      {catalog.status === 'ready' && candidates.length > 0 && <MenuBoard menus={candidates.flatMap(id => catalog.menus.filter(m => m.id === id))} selectedMenu={null} view={menuView} onViewChange={view => { interrupt(); setMenuView(view); }} onSelect={id => { const menu = catalog.menus.find(m => m.id === id && m.available); if(menu) choose(menu); }} />}
      <button className="primary-button" onClick={restart}>다시 추천받기</button>
    </section>}
    {stage === 'menu' && candidates === null && (catalog.status === 'ready'
      ? catalog.menus.length === 0 ? <CatalogStatus status="empty" onReload={reload} />
        : <MenuBoard groupByCategory menus={catalog.menus} selectedMenu={null}
          view={menuView} onViewChange={view => { interrupt(); setMenuView(view); }}
          onSelect={menuId => { const menu = catalog.menus.find(m => m.id === menuId && m.available); if (menu) choose(menu); }} />
      : catalog.status === 'loading' ? <CatalogStatus status="loading" />
        : <CatalogStatus status="error" message={catalog.message} onReload={() => { interrupt(); reload(); }} />)}
    {order.stage === 'temperature' && <TemperatureScreen menu={order.menu} onSelect={temperature => {
      interrupt(); const next = save(mergeVoiceOptions(sessionRef.current, { temperature }));
      dispatch({ type: 'set_temperature', temperature, voiceOptions: next }); }} />}
    {order.stage === 'customization' && <CustomizationScreen menu={order.menu} temperature={order.temperature}
      key={JSON.stringify(validated.customization)} initialSelectedIds={validated.customization?.option_ids ?? []}
      onSelectionChange={ids => { interrupt(); save({ ...sessionRef.current, customization: selectedCustomization(ids) }); }}
      onContinue={ids => { interrupt(); const next = save({ ...sessionRef.current, customization: selectedCustomization(ids) });
        dispatch({ type: 'set_options', ids, voiceOptions: next }); }} />}
    {order.stage === 'service_type' && <ServiceTypeScreen menu={order.menu} temperature={order.temperature} selectedOptions={order.selectedOptions}
      onSelect={serviceType => { interrupt(); const next = save(mergeVoiceOptions(sessionRef.current, { service_type: serviceType }));
        dispatch({ type: 'set_service_type', serviceType, voiceOptions: next }); }} />}
    {(order.stage === 'review' || order.stage === 'submitting') && <ReviewScreen draft={order.draft} isMock={isMockOrderApi} pending={order.stage === 'submitting'}
      error={order.stage === 'review' ? order.error : undefined} onConfirm={() => { interrupt(); void confirm(); }} />}
    {order.stage === 'complete' && <CompletionScreen draft={order.draft} result={order.result} isMock={isMockOrderApi} onHome={home} />}
  </KioskLayout>;
}
