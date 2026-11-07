export function microphoneUnavailableReason() {
  if (!window.isSecureContext) return '마이크는 HTTPS 또는 localhost에서 사용할 수 있어요.';
  if (!navigator.mediaDevices?.getUserMedia || typeof window.MediaRecorder !== 'function') {
    return '이 브라우저에서는 마이크 녹음을 지원하지 않아요.';
  }
}

export function microphoneErrorMessage(error: unknown) {
  if (error instanceof DOMException) {
    if (error.name === 'NotAllowedError') return '마이크 사용 권한을 허용해 주세요.';
    if (error.name === 'NotFoundError') return '연결된 마이크를 찾을 수 없어요.';
    if (error.name === 'NotReadableError') return '마이크 연결 상태나 다른 앱의 사용 여부를 확인해 주세요.';
  }
  return '마이크 녹음을 시작하지 못했어요.';
}

export async function startMicrophoneRecording(signal: AbortSignal, onInterrupted: () => void) {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const releaseTracks = () => stream.getTracks().forEach(track => track.stop());
  if (signal.aborted) {
    releaseTracks();
    return;
  }

  let recorder: MediaRecorder;
  try {
    recorder = new MediaRecorder(stream);
    // Emit small chunks so the recorder does not buffer the entire session.
    recorder.start(1000);
  } catch (error) {
    releaseTracks();
    throw error;
  }

  recorder.onstop = onInterrupted;
  recorder.onerror = onInterrupted;
  signal.addEventListener('abort', () => {
    recorder.onstop = null;
    recorder.onerror = null;
    try {
      if (recorder.state !== 'inactive') recorder.stop();
    } finally {
      releaseTracks();
    }
  }, { once: true });
}
