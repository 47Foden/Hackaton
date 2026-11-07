import { useEffect } from 'react';
import { browserVoiceGuidance } from '../voice/browserVoiceGuidance';

export function useVoiceGuidance(text: string) {
  useEffect(() => {
    browserVoiceGuidance.speak(text);
    return browserVoiceGuidance.cancel;
  }, [text]);
}
