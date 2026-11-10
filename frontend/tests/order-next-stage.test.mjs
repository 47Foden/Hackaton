import { test } from 'node:test';
import assert from 'node:assert/strict';
import { orderReducer, initialOrderState } from '../src/state/order.ts';
import { selectedCustomization } from '../src/state/voiceOptions.ts';

const shot = { id: 'shot:extra', label: '샷 추가', price_delta_krw: 600 };
const groups = [{ id: 'shot', label: '샷', max_selections: 1, choices: [shot,
  { id: 'shot:light', label: '연하게', price_delta_krw: 0 }] }];
const menu = { id: 'latte', name: '라떼', price: 4000, available: true,
  temperatures: ['HOT', 'COLD'], optionGroups: { HOT: groups, COLD: groups } };
const select = (voiceOptions, selectedMenu = menu) => orderReducer(initialOrderState,
  { type: 'select_menu', menu: selectedMenu, voiceOptions });

for (let flags = 0; flags < 8; flags++) {
  test(`first unresolved step for option combination ${flags}`, () => {
    const options = { ...(flags & 1 ? { temperature: 'COLD' } : {}),
      ...(flags & 2 ? { customization: selectedCustomization(['shot:extra']) } : {}),
      ...(flags & 4 ? { service_type: 'TAKEOUT' } : {}) };
    let state = select(options);
    assert.equal(state.stage, !(flags & 1) ? 'temperature' : !(flags & 2) ? 'customization' : !(flags & 4) ? 'service_type' : 'review');
    if (state.stage === 'temperature') state = orderReducer(state, { type: 'set_temperature', temperature: 'COLD' });
    if (state.stage === 'customization') state = orderReducer(state, { type: 'set_options', ids: ['shot:extra'] });
    if (state.stage === 'service_type') state = orderReducer(state, { type: 'set_service_type', serviceType: 'TAKEOUT' });
    assert.equal(state.stage, 'review');
    assert.equal(state.draft.serviceType, 'TAKEOUT');
    assert.deepEqual(state.draft.selectedOptions, [shot]);
    assert.equal(state.draft.temperature, 'COLD');
  });
}

test('empty resolved customization skips, while empty pending or ambiguous customization waits', () => {
  const options = { temperature: 'COLD', service_type: 'TAKEOUT' };
  assert.equal(select({ ...options, customization: selectedCustomization([]) }).stage, 'review');
  for (const status of ['pending', 'needs_clarification']) {
    assert.equal(select({ ...options, customization: { ...selectedCustomization([]), status } }).stage, 'customization');
  }
});

test('unsupported customization still asks even when menu has no option groups', () => {
  const noGroups = { ...menu, optionGroups: { HOT: [], COLD: [] } };
  assert.equal(select({ temperature: 'COLD', service_type: 'TAKEOUT' }, noGroups).stage, 'review');
  const state = select({ temperature: 'COLD', service_type: 'TAKEOUT', customization: selectedCustomization(['shot:extra']) }, noGroups);
  assert.equal(state.stage, 'customization');
  assert.deepEqual(state.selectedOptions, []);
  assert.equal(orderReducer(state, { type: 'set_options', ids: [] }).stage, 'review');
});

test('changing temperature revalidates original intent without retaining a derived error', () => {
  const variants = { ...menu, optionGroups: { HOT: [], COLD: groups } };
  let state = select({ temperature: 'HOT', service_type: 'TAKEOUT', customization: selectedCustomization(['shot:extra']) }, variants);
  assert.equal(state.stage, 'customization');
  state = orderReducer(state, { type: 'apply_voice_options', voiceOptions: { ...state.voiceOptions, temperature: 'COLD' } });
  assert.equal(state.stage, 'review');
  assert.deepEqual(state.draft.selectedOptions, [shot]);
});

test('service voice input preserves completed touch customization and explicit no-options', () => {
  for (const ids of [[], ['shot:extra']]) {
    let state = select({ temperature: 'COLD' });
    state = orderReducer(state, { type: 'set_options', ids });
    assert.equal(state.stage, 'service_type');
    state = orderReducer(state, { type: 'apply_voice_options', voiceOptions: { service_type: 'TAKEOUT' } });
    assert.equal(state.stage, 'review');
    assert.deepEqual(state.draft.selectedOptions.map(c => c.id), ids);
  }
});

test('invalid service values and conflicts cannot bypass the service step', () => {
  for (const patch of [{ service_type: 'INVALID' }, { service_type: 'TAKEOUT', unresolved_fields: ['service_type'] }]) {
    const state = select({ temperature: 'COLD', customization: selectedCustomization([]), ...patch });
    assert.equal(state.stage, 'service_type');
    assert.equal(orderReducer(state, { type: 'set_service_type', serviceType: 'DINE_IN' }).stage, 'review');
  }
});

test('duplicate and over-limit options require confirmation and cannot enter the draft', () => {
  for (const ids of [['shot:extra', 'shot:extra'], ['shot:extra', 'shot:light'], ['unknown:option']]) {
    const state = select({ temperature: 'COLD', service_type: 'TAKEOUT', customization: selectedCustomization(ids) });
    assert.equal(state.stage, 'customization');
    assert.strictEqual(orderReducer(state, { type: 'set_options', ids }), state);
  }
});

test('compound update during temperature step is atomic and does not mutate its input', () => {
  const state = select();
  const options = { temperature: 'COLD', service_type: 'TAKEOUT', customization: selectedCustomization(['shot:extra']) };
  const before = JSON.stringify({ state, options });
  const result = orderReducer(state, { type: 'apply_voice_options', voiceOptions: options });
  assert.equal(result.stage, 'review');
  assert.equal(JSON.stringify({ state, options }), before);
  assert.strictEqual(orderReducer(result, { type: 'apply_voice_options', voiceOptions: {} }), result);
});
