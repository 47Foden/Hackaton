import { useEffect, useRef, useState } from 'react';
import { browserVoiceGuidance } from '../voice/browserVoiceGuidance';
import { microphoneErrorMessage, startMicrophoneRecording } from '../voice/microphoneRecording';

type RecordingState =
  | { status: 'idle' | 'requesting' | 'recording' }
  | { status: 'error'; message: string };

export function useMicrophoneRecording() {
  const [state, setState] = useState<RecordingState>({ status: 'idle' });
  const active = useRef<AbortController | null>(null);

  useEffect(() => () => {
    active.current?.abort();
    active.current = null;
  }, []);

  async function start() {
    if (active.current) return;
    browserVoiceGuidance.cancel();

    const controller = new AbortController();
    active.current = controller;
    setState({ status: 'requesting' });
    try {
      await startMicrophoneRecording(controller.signal, () => {
        if (controller.signal.aborted) return;
        controller.abort();
        active.current = null;
        setState({ status: 'error', message: '마이크 녹음이 중단됐어요.' });
      });
      if (!controller.signal.aborted) setState({ status: 'recording' });
    } catch (error) {
      if (controller.signal.aborted) return;
      active.current = null;
      setState({ status: 'error', message: microphoneErrorMessage(error) });
    }
  }

  function stop() {
    if (!active.current) return false;
    active.current.abort();
    active.current = null;
    setState({ status: 'idle' });
    return true;
  }

  return { state, start, stop };
}
