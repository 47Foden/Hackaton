import { useMicrophoneRecording } from '../../hooks/useMicrophoneRecording';
import { microphoneUnavailableReason } from '../../voice/microphoneRecording';
import { MicrophoneButton } from './MicrophoneButton';

export function OrderMicrophone({ disabledReason, onRecordingComplete }: {
  disabledReason?: string;
  onRecordingComplete?: () => void;
}) {
  const { state, start, stop } = useMicrophoneRecording();
  const unavailable = disabledReason ?? microphoneUnavailableReason();

  if (unavailable) return <MicrophoneButton label="음성 녹음" disabled helpText={unavailable} />;
  if (state.status === 'requesting') {
    return <MicrophoneButton label="권한 확인 중…" disabled helpText="브라우저에서 마이크 사용을 허용해 주세요." />;
  }
  if (state.status === 'recording') {
    return <MicrophoneButton label="녹음 종료" helpText="녹음 중이에요." onClick={() => {
      if (stop()) onRecordingComplete?.();
    }} />;
  }
  return <MicrophoneButton label="음성 녹음" helpText={state.status === 'error' ? state.message : undefined} onClick={start} />;
}
