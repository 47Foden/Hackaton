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

export interface MicrophoneRecording {
  finish(): Promise<Blob>;
}

const maxRecordingBytes = 2 * 1024 * 1024;
const maxRecordingMs = 30_000;

export async function startMicrophoneRecording(signal: AbortSignal, onInterrupted: (message: string) => void)
  : Promise<MicrophoneRecording | undefined> {
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

  const chunks: Blob[] = [];
  let size = 0;
  let mimeType = recorder.mimeType;
  let completion: { resolve: (blob: Blob) => void; reject: (error: unknown) => void } | undefined;
  const recordingDeadline = window.setTimeout(() => {
    fail('녹음이 30초를 넘었어요. 30초 이내로 다시 녹음해 주세요.');
  }, maxRecordingMs);

  function release() {
    window.clearTimeout(recordingDeadline);
    signal.removeEventListener('abort', abort);
    recorder.onstart = null;
    recorder.ondataavailable = null;
    recorder.onstop = null;
    recorder.onerror = null;
    chunks.length = 0;
    releaseTracks();
  }

  function abort() {
    try {
      if (recorder.state !== 'inactive') recorder.stop();
    } finally {
      release();
      completion?.reject(signal.reason);
    }
  }

  function fail(message: string) {
    try {
      if (recorder.state !== 'inactive') recorder.stop();
    } finally {
      release();
      if (completion) completion.reject(new Error(message));
      else onInterrupted(message);
    }
  }

  recorder.onstart = () => { mimeType = recorder.mimeType; };
  recorder.ondataavailable = ({ data }) => {
    if (!data.size) return;
    size += data.size;
    if (size > maxRecordingBytes) {
      fail('녹음 파일이 2 MiB를 넘었어요. 짧게 다시 녹음해 주세요.');
      return;
    }
    chunks.push(data);
  };
  recorder.onstop = () => {
    if (!completion) {
      fail('마이크 녹음이 중단됐어요.');
      return;
    }
    const audio = new Blob(chunks, { type: chunks[0]?.type || mimeType });
    release();
    completion.resolve(audio);
  };
  recorder.onerror = () => fail('마이크 녹음이 중단됐어요.');
  signal.addEventListener('abort', abort, { once: true });

  return {
    finish: () => new Promise<Blob>((resolve, reject) => {
      window.clearTimeout(recordingDeadline);
      completion = { resolve, reject };
      try {
        recorder.stop();
      } catch {
        fail('녹음을 완료하지 못했어요.');
      }
    }),
  };
}
