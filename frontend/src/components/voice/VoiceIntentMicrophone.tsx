import { useId, useRef } from 'react';
import { useMicrophoneRecording } from '../../hooks/useMicrophoneRecording';
import { microphoneUnavailableReason } from '../../voice/microphoneRecording';
import { MicrophoneButton } from './MicrophoneButton';
import './VoiceIntentMicrophone.css';
import type { VoiceIntent } from '../../voice/voiceIntent';

export type { VoiceIntent } from '../../voice/voiceIntent';
export type IntentRecordingComplete = (audio: Blob, signal: AbortSignal, intent: VoiceIntent) => void | Promise<void>;

export function VoiceIntentMicrophone({ disabledReason, onRecordingComplete }: {
  disabledReason?: string;
  onRecordingComplete: IntentRecordingComplete;
}) {
  const activeIntent = useRef<VoiceIntent>('order');
  const { state, start, stop, isActive } = useMicrophoneRecording((audio, signal) =>
    onRecordingComplete(audio, signal, activeIntent.current));
  const helpId = useId();
  const unavailable = disabledReason ?? microphoneUnavailableReason();
  const busy = ['requesting', 'recording', 'processing'].includes(state.status);
  const help = unavailable ?? (state.status === 'error' ? state.message
    : state.status === 'requesting' ? '브라우저에서 마이크 사용을 허용해 주세요.'
    : state.status === 'recording' ? '말씀하신 뒤 녹음 종료를 눌러 주세요.'
    : state.status === 'processing' ? '잠시만 기다려 주세요.' : undefined);

  function begin(intent: VoiceIntent) {
    // Ref guard runs before React renders disabled buttons, preventing two
    // permission requests and a second click changing the first request's intent.
    if (unavailable || isActive()) return;
    activeIntent.current = intent;
    void start((audio, signal) => onRecordingComplete(audio, signal, intent));
  }

  return <div className="voice-intent-control" role="group" aria-label="음성 입력 목적">
    <div className="voice-intent-control__buttons">
      {(['order', 'recommend'] as const).map(intent => {
        const active = intent === activeIntent.current;
        const label = active && busy
          ? state.status === 'requesting' ? '권한 확인 중…' : state.status === 'recording' ? '녹음 종료' : '음성 처리 중…'
          : intent === 'order' ? '주문하기' : '메뉴 추천받기';
        const disabled = Boolean(unavailable) || (busy && !(active && state.status === 'recording'));
        return disabled
          ? <MicrophoneButton key={intent} label={label} disabled describedBy={help ? helpId : undefined} />
          : <MicrophoneButton key={intent} label={label} describedBy={help ? helpId : undefined}
              onClick={() => { if (state.status === 'recording') void stop(); else begin(intent); }} />;
      })}
    </div>
    {help && <p id={helpId} role="status" className="voice-intent-control__help">{help}</p>}
  </div>;
}
