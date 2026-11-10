import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mergeVoiceOptions, validateVoiceOptions, selectedCustomization, readVoiceOptions } from '../src/state/voiceOptions.ts';
import { orderReducer, initialOrderState } from '../src/state/order.ts';

const groups = [{ id: 'shot', label: '샷', max_selections: 1, choices: [
  { id: 'shot:extra', label: '샷 추가', price_delta_krw: 600 }, { id: 'shot:light', label: '연하게', price_delta_krw: 0 }] },
{ id: 'sweetness', label: '시럽', max_selections: 1, choices: [{ id: 'sweetness:vanilla', label: '바닐라', price_delta_krw: 700 }] }];
const menu = { id: 'latte', name: '라떼', available: true, temperatures: ['HOT', 'COLD'], optionGroups: { HOT: groups, COLD: groups } };
const custom = (...ids) => selectedCustomization(ids);

test('omitted fields survive confirmation; same-group corrections retain other groups', () => {
  let options = { temperature: 'COLD', service_type: 'TAKEOUT', customization: custom('shot:extra', 'sweetness:vanilla') };
  assert.equal(mergeVoiceOptions(options, undefined), options);
  options = mergeVoiceOptions(options, { customization: custom('shot:light') });
  assert.equal(options.temperature, 'COLD');
  assert.equal(options.service_type, 'TAKEOUT');
  assert.deepEqual(validateVoiceOptions(options, menu).customization.option_ids, ['sweetness:vanilla', 'shot:light']);
  assert.deepEqual(mergeVoiceOptions(options, { customization: custom() }).customization.option_ids, []);
});

test('conflicting scalar clears prior choice until explicitly selected again', () => {
  const value = mergeVoiceOptions({ temperature: 'COLD' }, { unresolved_fields: ['temperature'] });
  assert.equal(value.temperature, undefined);
  assert.deepEqual(value.unresolved_fields, ['temperature']);
  assert.deepEqual(mergeVoiceOptions(value, { temperature: 'HOT' }).unresolved_fields, []);
});

test('pending intents revalidate per menu and temperature without losing original intent', () => {
  const raw = { customization: { ...custom('shot:extra'), status: 'pending', option_ids: [] } };
  assert.equal(validateVoiceOptions(raw, menu).customization.status, 'pending');
  assert.deepEqual(validateVoiceOptions(raw, menu, 'COLD').customization.option_ids, ['shot:extra']);
  const incompatible = { ...menu, optionGroups: { HOT: [], COLD: [] } };
  assert.equal(validateVoiceOptions(raw, incompatible, 'COLD').customization.status, 'needs_clarification');
  assert.equal(validateVoiceOptions(raw, menu, 'HOT').customization.status, 'resolved');
});

test('one reducer transition applies a compound order without intermediate screens', () => {
  const state = orderReducer(initialOrderState, { type: 'select_menu', menu,
    voiceOptions: { temperature: 'COLD', service_type: 'TAKEOUT', customization: custom('shot:extra') } });
  assert.equal(state.stage, 'review');
  assert.equal(state.draft.temperature, 'COLD');
  assert.equal(state.draft.serviceType, 'TAKEOUT');
  assert.equal(state.draft.selectedOptions[0].price_delta_krw, 600);
});

test('pending customization and service type survive a later touch temperature choice', () => {
  let state = orderReducer(initialOrderState, { type: 'select_menu', menu,
    voiceOptions: { service_type: 'TAKEOUT', customization: { ...custom('shot:extra'), status: 'pending', option_ids: [] } } });
  assert.equal(state.stage, 'temperature');
  state = orderReducer(state, { type: 'set_temperature', temperature: 'HOT' });
  assert.equal(state.stage, 'review');
  assert.deepEqual(state.draft.selectedOptions.map(o => o.id), ['shot:extra']);
});

test('ambiguous options show valid selections and require explicit touch completion', () => {
  let state = orderReducer(initialOrderState, { type: 'select_menu', menu,
    voiceOptions: { temperature: 'COLD', service_type: 'TAKEOUT', customization: {
      ...custom('shot:extra'), status: 'needs_clarification', unresolved: ['시럽'] } } });
  assert.equal(state.stage, 'customization');
  assert.deepEqual(state.voiceOptions.customization.option_ids, ['shot:extra']);
  state = orderReducer(state, { type: 'set_options', ids: ['shot:extra', 'sweetness:vanilla'] });
  assert.equal(state.stage, 'review');
  assert.equal(state.draft.selectedOptions.length, 2);
});

test('unsupported temperature is never silently substituted, even for single-temperature menu', () => {
  const state = orderReducer(initialOrderState, { type: 'select_menu', menu: { ...menu, temperatures: ['HOT'] },
    voiceOptions: { temperature: 'COLD', service_type: 'TAKEOUT' } });
  assert.equal(state.stage, 'temperature');
});

test('malformed response options are rejected', () => {
  assert.throws(() => readVoiceOptions({ customization: { status: 'resolved' } }));
  assert.throws(() => readVoiceOptions({ temperature: 'ICE' }));
  assert.equal(readVoiceOptions(undefined), undefined);
});
