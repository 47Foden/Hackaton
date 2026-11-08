import { MicrophoneIcon } from '../components/MicrophoneIcon';
import { BrandLogo } from '../components/BrandLogo';

export function StartScreen({ onStart, onVoice }: { onStart: () => void; onVoice: () => void }) {
  return (
    <main className="start-screen" aria-label="주문 시작">
      <div className="start-screen__content">
        <BrandLogo />
        <button className="primary-button start-screen__button" type="button" onClick={onStart}>
          주문하기 <span aria-hidden="true">→</span>
        </button>
        <p className="start-screen__voice-guide">터치뿐 아니라 음성으로도 주문할 수 있어요.</p>
        <button className="primary-button start-screen__button start-screen__voice-button" type="button" onClick={onVoice}><MicrophoneIcon /><span>음성으로 주문하기</span></button>
      </div>
    </main>
  );
}
