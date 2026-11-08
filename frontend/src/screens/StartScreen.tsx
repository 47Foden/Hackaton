import { useVoiceGuidance } from '../hooks/useVoiceGuidance';
import { browserVoiceGuidance } from '../voice/browserVoiceGuidance';
import { MicrophoneIcon } from '../components/MicrophoneIcon';
import { BrandLogo } from '../components/BrandLogo';

export function StartScreen({ onStart, onVoice }: { onStart: () => void; onVoice: () => void }) {
  const message = '음성으로 주문 안내나 메뉴 추천을 받고 싶거나, 메뉴를 골라 터치하는 방식이 불편하신 분들은 음성 주문 기능을 사용해 주세요.';
  useVoiceGuidance(message);
  return (
    <main className="start-screen" aria-label="주문 시작">
      <div className="start-screen__content">
        <BrandLogo />
        <button className="primary-button start-screen__button" type="button" onClick={() => { browserVoiceGuidance.cancel(); onStart(); }}>
          주문하기 <span aria-hidden="true">→</span>
        </button>
        <p className="start-screen__voice-guide">{message}</p>
        <button className="text-button" onClick={() => { browserVoiceGuidance.cancel(); browserVoiceGuidance.speak(message); }}>안내 다시 듣기</button>
        <button className="primary-button start-screen__button start-screen__voice-button" type="button" onClick={() => { browserVoiceGuidance.cancel(); onVoice(); }}><MicrophoneIcon /><span>음성으로 주문하기</span></button>
      </div>
    </main>
  );
}
