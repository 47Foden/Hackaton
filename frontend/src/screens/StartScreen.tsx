import { BrandLogo } from '../components/BrandLogo';

export function StartScreen({ onStart }: { onStart: () => void }) {
  return (
    <main className="start-screen" aria-label="주문 시작">
      <div className="start-screen__content">
        <BrandLogo />
        <button className="primary-button start-screen__button" type="button" onClick={onStart}>
          주문하기 <span aria-hidden="true">→</span>
        </button>
      </div>
    </main>
  );
}
