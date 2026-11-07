import { test } from 'node:test';
import assert from 'node:assert/strict';
import { initialOrderState, orderReducer } from '../src/state/order.ts';

const menu = (temperatures) => ({
  id: 'test', available: true, featured: false, name: '테스트 음료', price: 2900, temperatures,
  imageUrl: '/test.jpg', imageUrls: { HOT: '/hot.jpg', COLD: '/cold.jpg' },
});

test('two-temperature order requires temperature and service type before confirmation', () => {
  let state = orderReducer(initialOrderState, { type: 'select_menu', menu: menu(['HOT', 'COLD']) });
  assert.equal(state.stage, 'temperature');
  assert.strictEqual(orderReducer(state, { type: 'submit' }), state);
  state = orderReducer(state, { type: 'set_temperature', temperature: 'HOT' });
  assert.equal(state.stage, 'service_type');
  state = orderReducer(state, { type: 'set_service_type', serviceType: 'DINE_IN' });
  assert.equal(state.stage, 'review');
  assert.deepEqual([state.draft.temperature, state.draft.serviceType, state.draft.menu.price], ['HOT', 'DINE_IN', 2900]);
  state = orderReducer(state, { type: 'submit' });
  assert.equal(state.stage, 'submitting');
  state = orderReducer(state, { type: 'submitted', result: { order_number: 'DEV-0001' } });
  assert.equal(state.stage, 'complete');
  assert.strictEqual(orderReducer(state, { type: 'submit' }), state);
});

for (const temperature of ['HOT', 'COLD']) {
  test(`${temperature}-only menu skips temperature question but preserves the option`, () => {
    let state = orderReducer(initialOrderState, { type: 'select_menu', menu: menu([temperature]) });
    assert.equal(state.stage, 'service_type');
    assert.equal(state.temperature, temperature);
    assert.strictEqual(orderReducer(state, { type: 'set_temperature', temperature: temperature === 'HOT' ? 'COLD' : 'HOT' }), state);
    state = orderReducer(state, { type: 'set_service_type', serviceType: 'TAKEOUT' });
    assert.equal(state.stage, 'review');
    assert.equal(state.draft.temperature, temperature);
    assert.equal(state.draft.serviceType, 'TAKEOUT');
  });
}

test('invalid stage, unsupported temperature, and empty menu options cannot advance', () => {
  assert.strictEqual(orderReducer(initialOrderState, { type: 'submit' }), initialOrderState);
  assert.strictEqual(orderReducer(initialOrderState, { type: 'select_menu', menu: menu([]) }), initialOrderState);
  const state = orderReducer(initialOrderState, { type: 'select_menu', menu: menu(['HOT', 'COLD']) });
  assert.strictEqual(orderReducer(state, { type: 'set_temperature', temperature: 'WARM' }), state);
  assert.strictEqual(orderReducer(state, { type: 'set_service_type', serviceType: 'TAKEOUT' }), state);
});


test('submission failure never completes and uncertain outcomes block resubmission', () => {
  let state = orderReducer(initialOrderState, { type: 'select_menu', menu: menu(['COLD']) });
  state = orderReducer(state, { type: 'set_service_type', serviceType: 'TAKEOUT' });
  state = orderReducer(state, { type: 'submit' });
  state = orderReducer(state, { type: 'failed', error: { message: '불명확', uncertain: true } });
  assert.equal(state.stage, 'review');
  assert.strictEqual(orderReducer(state, { type: 'submit' }), state);
  assert.strictEqual(orderReducer(state, { type: 'submitted', result: {} }), state);
});
