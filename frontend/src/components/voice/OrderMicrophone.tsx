import { useMicrophoneRecording, type RecordingComplete } from '../../hooks/useMicrophoneRecording';
import { microphoneUnavailableReason } from '../../voice/microphoneRecording';
import { MicrophoneButton } from './MicrophoneButton';

export function OrderMicrophone({ disabledReason, onRecordingComplete }: {
  disabledReason?: string;
  onRecordingComplete: RecordingComplete;
}) {
  const { state, start, stop } = useMicrophoneRecording(onRecordingComplete);
  const unavailable = disabledReason ?? microphoneUnavailableReason();

  if (unavailable) return <MicrophoneButton label="음성 녹음" disabled helpText={unavailable} />;
  if (state.status === 'requesting') {
    return <MicrophoneButton label="권한 확인 중…" disabled helpText="브라우저에서 마이크 사용을 허용해 주세요." />;
  }
  if (state.status === 'recording') {
    return <MicrophoneButton label="녹음 종료" helpText="말씀하신 뒤 녹음 종료를 눌러 주세요." onClick={stop} />;
  }
  if (state.status === 'processing') {
    return <MicrophoneButton label="음성 처리 중…" disabled helpText="잠시만 기다려 주세요." />;
  }
  const helpText = state.status === 'error' ? state.message : state.status === 'ready' ? '녹음 파일을 확인했어요.' : undefined;
  return <MicrophoneButton label={state.status === 'error' ? '다시 녹음' : '음성 녹음'} helpText={helpText} onClick={start} />;
}
