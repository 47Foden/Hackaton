import { test } from 'node:test';
import assert from 'node:assert/strict';
import { acceptsVoiceAction, voiceRetryMessage } from '../src/voice/voiceIntent.ts';

test('only purpose-specific actions and explicit restart/retry may pass', () => {
  for (const intent of ['order', 'recommend']) {
    for (const type of ['select_menu', 'direct_recommendation', 'restart_recommendation', 'retry',
      'confirm', 'set_temperature', 'set_options', undefined, null, 'unknown']) {
      const expected = ['retry', 'restart_recommendation', intent === 'order' ? 'select_menu' : 'direct_recommendation'].includes(type);
      assert.equal(acceptsVoiceAction(intent, type), expected, `${intent}: ${type}`);
    }
  }
});

test('retry messages distinguish purpose and actionable failure reason', () => {
  assert.match(voiceRetryMessage('order', 'UNRECOGNIZED'), /메뉴 이름.*메뉴 추천받기/);
  assert.match(voiceRetryMessage('recommend', 'UNRECOGNIZED'), /추천 조건/);
  assert.match(voiceRetryMessage('order', 'MENU_UNAVAILABLE'), /주문할 수 없는/);
  assert.match(voiceRetryMessage('order', 'OUTSIDE_CANDIDATES'), /현재 추천 목록/);
  assert.match(voiceRetryMessage('recommend', 'EMPTY_TRANSCRIPT'), /음성이 들리지/);
  assert.match(voiceRetryMessage(), /화면에서 선택/);
});
