import { ApiError, asApiError } from './errors';

const audioCheckTimeoutMs = 15_000;

export async function prepareVoiceAudio(audio: Blob, signal: AbortSignal) {
  if (!audio.size) throw new ApiError('녹음된 음성이 없어요.', 422, 'EMPTY_AUDIO');
  if (!['audio/webm', 'audio/webm;codecs=opus'].includes(audio.type)) {
    throw new ApiError('이 브라우저에서 만든 녹음 형식은 지원하지 않아요.', 415, 'UNSUPPORTED_AUDIO');
  }

  const body = new FormData();
  body.set('audio', audio, 'recording.webm');
  const timeout = AbortSignal.timeout(audioCheckTimeoutMs);
  try {
    const response = await fetch('/api/voice/audio', {
      method: 'POST', body, signal: AbortSignal.any([signal, timeout]),
    });
    if (response.ok) return;
    const payload = await response.json().catch(() => null);
    throw new ApiError(payload?.detail?.message ?? '녹음 파일을 확인하지 못했어요.', response.status,
      payload?.detail?.code ?? 'HTTP_ERROR');
  } catch (error) {
    if (timeout.aborted) {
      throw new ApiError('녹음 파일 확인 시간이 초과됐어요. 짧게 다시 녹음해 주세요.', 0, 'AUDIO_TIMEOUT');
    }
    throw asApiError(error);
  }
}
