export type VoiceIntent = 'order' | 'recommend';

export function acceptsVoiceAction(intent: VoiceIntent, type: unknown): boolean {
  return type === 'retry' || type === 'restart_recommendation'
    || type === (intent === 'order' ? 'select_menu' : 'direct_recommendation');
}

export function voiceRetryMessage(intent?: VoiceIntent, reason?: string): string {
  if (reason === 'EMPTY_TRANSCRIPT') return '음성이 들리지 않았어요. 버튼을 누르고 다시 말씀해 주세요.';
  if (intent === 'order') {
    if (reason === 'MENU_UNAVAILABLE') return '현재 주문할 수 없는 메뉴예요. 다른 메뉴를 선택해 주세요.';
    if (reason === 'OUTSIDE_CANDIDATES') return '현재 추천 목록에서 메뉴를 선택하거나 메뉴 추천받기를 눌러 주세요.';
    return '메뉴 이름을 확인하지 못했어요. 다시 말씀하시거나 메뉴 추천받기를 눌러 주세요.';
  }
  if (intent === 'recommend') return '추천 조건을 이해하지 못했어요. 메뉴 추천받기를 누르고 원하는 음료를 다시 말씀해 주세요.';
  return '입력을 이해하지 못했어요. 다시 말씀하시거나 화면에서 선택해 주세요.';
}
