import { useEffect, useRef, useState, type FormEvent } from 'react';
import './RecommendationTextTest.css';

type Engine = 'existing' | 'llm-v3';
interface Config { llm_enabled: boolean; api_key_configured: boolean; model: string }
interface Candidate { menu_id: string; name: string; price_krw: number; temperature: string | null; reason: string }
interface Reply {
  engine: Engine; transcript: string; model: string | null; api_calls: number;
  latency_ms: number; cost_usd_estimate: number | null;
  usage: { input_tokens?: number; output_tokens?: number } | null;
  result: { status: 'recommend' | 'clarify' | 'insufficient_data'; recommendations: Candidate[];
    questions: string[]; missing_information: string[] };
}
const samples = [
  '커피는 빼고, 3,000원 이하인 차가운 음료를 추천해 주세요.',
  '레몬의 산미와 탄산이 있는 차가운 음료를 3,500원 이하로 추천해 주세요.',
  '딸기 맛과 우유가 들어간 차가운 음료를 4,000원 이하로 추천해 주세요.',
];

export function RecommendationTextTest({ disabled, onShowCandidates }: {
  disabled: boolean; onShowCandidates: (ids: string[]) => void;
}) {
  const [text, setText] = useState('');
  const [engine, setEngine] = useState<Engine>('existing');
  const [config, setConfig] = useState<Config | null>(null);
  const [configError, setConfigError] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [reply, setReply] = useState<Reply | null>(null);
  const request = useRef<AbortController | null>(null);
  const llmReady = config?.llm_enabled && config.api_key_configured;

  async function refresh(signal?: AbortSignal) {
    try {
      const response = await fetch('/api/experiments/recommend-text', { signal });
      if (!response.ok) throw new Error();
      setConfig(await response.json()); setConfigError('');
    } catch {
      if (!signal?.aborted) {
        setConfig(null);
        setConfigError('텍스트 시험 API에 연결하지 못했어요. 새 백엔드가 실행 중인지 확인해 주세요.');
      }
    }
  }
  useEffect(() => {
    const controller = new AbortController();
    void refresh(controller.signal);
    return () => { controller.abort(); request.current?.abort(); };
  }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (request.current || disabled || !text.trim() || (engine === 'llm-v3' && !llmReady)) return;
    const controller = new AbortController();
    request.current = controller;
    setPending(true); setError(''); setReply(null);
    try {
      const response = await fetch('/api/experiments/recommend-text', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ transcript: text.trim(), engine, paid_call_confirmed: engine === 'llm-v3' }),
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(60_000)]),
      });
      const data = await response.json();
      if (controller.signal.aborted) return;
      if (!response.ok) throw new Error(`${data?.detail?.message ?? '추천 시험을 처리하지 못했어요.'}${data?.detail?.code ? ` (${data.detail.code})` : ''}`);
      setReply(data as Reply);
    } catch (failure) {
      if (controller.signal.aborted) return;
      setError(failure instanceof Error && failure.name !== 'TimeoutError' ? failure.message
        : '처리 시간이 초과됐어요. 자동 재시도하지 않았습니다. LLM 호출은 처리·과금됐을 수 있으니 상태 확인 후 다시 실행해 주세요.');
    } finally {
      if (request.current === controller) { request.current = null; setPending(false); }
    }
  }

  return <details className="recommendation-text-test">
    <summary>텍스트로 추천 시험 (개발용)</summary>
    <p>녹음 대신 발화를 입력해 추천을 확인합니다. 현재 녹음 경로는 기존 방식이며, 아래에서만 LLM v3를 별도로 선택합니다.</p>
    <p>음성 인식·질문 후 대화는 시험하지 않습니다. 질문에 답하려면 조건을 합쳐 새 문장으로 입력해 주세요.</p>
    {configError && <p role="alert">{configError}</p>}
    {config && <p>LLM 서버 설정: {config.llm_enabled ? '켜짐' : '꺼짐'} / API 키: {config.api_key_configured ? '서버에 설정됨' : '서버에 미설정'} / 모델: {config.model}</p>}
    <button type="button" onClick={() => { void refresh(); }} disabled={pending}>서버 설정 다시 확인</button>
    <form onSubmit={event => { void submit(event); }}>
      <label htmlFor="text-test-engine">추천 방식</label>
        <select id="text-test-engine" value={engine} onChange={event => { setEngine(event.target.value as Engine); setReply(null); setError(''); }} disabled={pending}>
          <option value="existing">기존 방식 (기본 · API 호출 없음)</option>
          <option value="llm-v3" disabled={!llmReady}>LLM v3 (유료 API 1회 호출)</option>
        </select>
      <label htmlFor="text-test-transcript">시험할 발화</label>
        <textarea id="text-test-transcript" value={text} onChange={event => setText(event.target.value)} maxLength={4000}
          rows={3} placeholder="예: 레몬의 산미와 탄산이 있는 차가운 음료를 추천해 주세요."
          disabled={pending} required />
      <div className="recommendation-text-test__samples" aria-label="발화 예시">
        {samples.map((sample, index) => <button key={sample} type="button" disabled={pending}
          onClick={() => setText(sample)}>예시 {index + 1}</button>)}
      </div>
      {engine === 'llm-v3' && <p>실행 버튼을 누르면 서버에서 유료 API를 1회 호출합니다. 자동 재시도는 없으며, 키는 이 화면에 입력하지 않습니다.</p>}
      <button type="submit" className="primary-button" disabled={pending || disabled || !text.trim() || (engine === 'llm-v3' && !llmReady)}>
        {pending ? '추천 확인 중…' : engine === 'llm-v3' ? 'LLM v3 실행 · 유료 API 1회' : '기존 방식으로 추천 시험'}
      </button>
    </form>
    {error && <p role="alert">{error}</p>}
    {reply && <section aria-label="텍스트 추천 시험 결과" aria-live="polite">
      <h2>{reply.engine === 'llm-v3' ? 'LLM v3 결과' : '기존 방식 결과'}</h2>
      <p>시험한 발화: {reply.transcript}</p>
      {reply.result.status === 'clarify' && <h3>추가 질문</h3>}
      {reply.result.questions.map(question => <p key={question}>{question}</p>)}
      {reply.result.status === 'insufficient_data' && <h3>자료가 부족해 추천을 보류했어요.</h3>}
      {reply.result.missing_information.map(message => <p key={message}>{message}</p>)}
      {reply.result.recommendations.map(candidate => <article key={candidate.menu_id}>
        <h3>{candidate.name} · {candidate.price_krw.toLocaleString('ko-KR')}원 {candidate.temperature}</h3>
        <p>{candidate.reason}</p>
      </article>)}
      <p>응답시간 {Math.round(reply.latency_ms)}ms / API {reply.api_calls}회
        {reply.model ? ` / 모델 ${reply.model}` : ''}
        {reply.usage ? ` / 입력 ${reply.usage.input_tokens}·출력 ${reply.usage.output_tokens}토큰` : ''}
        {reply.cost_usd_estimate !== null ? ` / 추정 $${reply.cost_usd_estimate.toFixed(6)}` : ' / 비용 미상'}</p>
      {reply.result.recommendations.length > 0 && <button type="button" className="primary-button"
        onClick={() => onShowCandidates(reply.result.recommendations.map(candidate => candidate.menu_id))}>
        이 추천을 메뉴 선택 화면에 표시
      </button>}
    </section>}
  </details>;
}
