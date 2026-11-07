export const browserVoiceGuidance = {
  speak(text: string) {
    if (!window.speechSynthesis || typeof window.SpeechSynthesisUtterance !== 'function') return;

    try {
      const utterance = new window.SpeechSynthesisUtterance(text);
      utterance.lang = 'ko-KR';
      window.speechSynthesis.speak(utterance);
    } catch {
      // The on-screen guide remains available if the speech engine fails.
    }
  },

  cancel() {
    window.speechSynthesis?.cancel();
  },
};
