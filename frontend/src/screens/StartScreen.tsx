import { BrandLogo } from '../components/BrandLogo';

export function StartScreen({ onStart, onVoice }: { onStart: () => void; onVoice: () => void }) {
  return (
    <main className="start-screen" aria-label="주문 시작">
      <div className="start-screen__content">
        <BrandLogo />
        <button className="primary-button start-screen__button" type="button" onClick={onStart}>
          주문하기 <span aria-hidden="true">→</span>
        </button>
        <button className="primary-button" type="button" onClick={onVoice}>음성으로 주문하기</button>
      </div>
    </main>
  );
}
