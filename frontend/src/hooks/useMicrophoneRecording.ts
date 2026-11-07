import { useEffect, useRef, useState } from 'react';
import { browserVoiceGuidance } from '../voice/browserVoiceGuidance';
import { microphoneErrorMessage, startMicrophoneRecording, type MicrophoneRecording } from '../voice/microphoneRecording';

type RecordingState =
  | { status: 'idle' | 'requesting' | 'recording' | 'processing' | 'ready' }
  | { status: 'error'; message: string };

export type RecordingComplete = (audio: Blob, signal: AbortSignal) => void | Promise<void>;

interface RecordingRequest {
  controller: AbortController;
  recording?: MicrophoneRecording;
}

export function useMicrophoneRecording(onRecordingComplete: RecordingComplete) {
  const [state, setState] = useState<RecordingState>({ status: 'idle' });
  const active = useRef<RecordingRequest | null>(null);

  useEffect(() => () => {
    active.current?.controller.abort();
    active.current = null;
  }, []);

  async function start() {
    if (active.current) return;
    browserVoiceGuidance.cancel();

    const controller = new AbortController();
    const request: RecordingRequest = { controller };
    active.current = request;
    setState({ status: 'requesting' });
    try {
      request.recording = await startMicrophoneRecording(controller.signal, message => {
        if (controller.signal.aborted) return;
        controller.abort();
        active.current = null;
        setState({ status: 'error', message });
      });
      if (request.recording && !controller.signal.aborted) setState({ status: 'recording' });
    } catch (error) {
      if (controller.signal.aborted) return;
      active.current = null;
      setState({ status: 'error', message: microphoneErrorMessage(error) });
    }
  }

  async function stop() {
    const request = active.current;
    const recording = request?.recording;
    if (!request || !recording) return;
    const { signal } = request.controller;
    request.recording = undefined;
    setState({ status: 'processing' });
    try {
      const audio = await recording.finish();
      if (signal.aborted) return;
      await onRecordingComplete(audio, signal);
      if (!signal.aborted) setState({ status: 'ready' });
    } catch (error) {
      if (!signal.aborted) {
        setState({ status: 'error', message: error instanceof Error ? error.message : '녹음을 처리하지 못했어요.' });
      }
    } finally {
      if (active.current === request) active.current = null;
    }
  }

  return { state, start, stop };
}
