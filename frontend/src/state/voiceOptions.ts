import type { Menu, Temperature } from '../data/menuCatalog.ts';
import type { ServiceType } from '../api/contracts.ts';

export interface CustomizationIntent { expression: string; candidate_option_ids: string[]; }
export interface VoiceCustomization {
  status: 'resolved' | 'pending' | 'needs_clarification';
  option_ids: string[];
  intents: CustomizationIntent[];
  unresolved: string[];
}
export interface VoiceOptions {
  temperature?: Temperature;
  service_type?: ServiceType;
  customization?: VoiceCustomization;
  unresolved_fields?: ('temperature' | 'service_type')[];
}

export function readVoiceOptions(value: unknown): VoiceOptions | undefined {
  if (value === undefined) return undefined;
  const v = value as VoiceOptions;
  const strings = (x: unknown): x is string[] => Array.isArray(x) && x.every(i => typeof i === 'string');
  if (!v || typeof v !== 'object'
    || (v.temperature !== undefined && !['HOT', 'COLD'].includes(v.temperature))
    || (v.service_type !== undefined && !['DINE_IN', 'TAKEOUT'].includes(v.service_type))
    || (v.unresolved_fields !== undefined && (!strings(v.unresolved_fields)
      || v.unresolved_fields.some(f => !['temperature', 'service_type'].includes(f))))) throw new Error('음성 옵션을 확인하지 못했어요.');
  const c = v.customization;
  if (c !== undefined && (!c || !['resolved', 'pending', 'needs_clarification'].includes(c.status)
    || !strings(c.option_ids) || !strings(c.unresolved) || !Array.isArray(c.intents)
    || !c.intents.every(i => i && typeof i.expression === 'string' && strings(i.candidate_option_ids)))) {
    throw new Error('음성 추가 옵션을 확인하지 못했어요.');
  }
  return v;
}

const groupsOf = (intent: CustomizationIntent) => intent.candidate_option_ids.map(id => id.split(':')[0]);
export function mergeVoiceOptions(previous: VoiceOptions, incoming?: VoiceOptions): VoiceOptions {
  if (!incoming) return previous;
  const next = { ...previous };
  const unresolved = new Set(previous.unresolved_fields ?? []);
  for (const field of ['temperature', 'service_type'] as const) {
    if (incoming.unresolved_fields?.includes(field)) { delete next[field]; unresolved.add(field); }
    else if (incoming[field]) {
      Object.assign(next, { [field]: incoming[field] }); unresolved.delete(field);
    }
  }
  next.unresolved_fields = [...unresolved];
  if (incoming.customization) {
    const c = incoming.customization;
    // Explicit "no options" clears all groups; otherwise update only mentioned groups.
    if (c.status === 'resolved' && !c.intents.length && !c.option_ids.length) next.customization = c;
    else {
      const old = previous.customization;
      const touched = new Set(c.intents.flatMap(groupsOf));
      const retained = (old?.intents ?? []).filter(i => !groupsOf(i).some(g => touched.has(g)));
      next.customization = { ...c, intents: [...retained, ...c.intents],
        option_ids: [...(old?.option_ids ?? []).filter(id => !touched.has(id.split(':')[0])), ...c.option_ids],
        // Unknown expressions require explicit confirmation on the customization screen.
        unresolved: [...new Set([...(old?.unresolved ?? []), ...c.unresolved])] };
    }
  }
  return next;
}

export function validateVoiceOptions(options: VoiceOptions, menu: Menu, temperature?: Temperature): VoiceOptions {
  const result = { ...options, unresolved_fields: [...(options.unresolved_fields ?? [])] };
  if (options.temperature && !menu.temperatures.includes(options.temperature)) {
    result.unresolved_fields = [...new Set([...result.unresolved_fields, 'temperature' as const])];
  }
  const selected = temperature ?? options.temperature ?? (menu.temperatures.length === 1 ? menu.temperatures[0] : undefined);
  const c = options.customization;
  if (!c) return result;
  if (!selected || !menu.temperatures.includes(selected)) {
    result.customization = { ...c, status: c.unresolved.length ? 'needs_clarification' : 'pending', option_ids: [] };
    return result;
  }
  const groups = menu.optionGroups?.[selected] ?? [];
  const available = new Set(groups.flatMap(g => g.choices.map(choice => choice.id)));
  const unresolved = [...c.unresolved];
  const ids: string[] = [];
  const intents = c.intents.length ? c.intents : c.option_ids.map(id => ({ expression: id, candidate_option_ids: [id] }));
  for (const intent of intents) {
    const matches = intent.candidate_option_ids.filter(id => available.has(id));
    if (matches.length !== 1 || ids.includes(matches[0])) unresolved.push(intent.expression);
    else ids.push(matches[0]);
  }
  const invalid = new Set<string>();
  for (const group of groups) {
    const selectedIds = ids.filter(id => group.choices.some(c => c.id === id));
    if (selectedIds.length > group.max_selections) {
      unresolved.push(group.label); selectedIds.forEach(id => invalid.add(id));
    }
  }
  result.customization = { ...c, option_ids: ids.filter(id => !invalid.has(id)),
    status: unresolved.length ? 'needs_clarification' : !intents.length && c.status !== 'resolved' ? c.status : 'resolved',
    unresolved: [...new Set(unresolved)] };
  return result;
}

export function selectedCustomization(ids: string[]): VoiceCustomization {
  return { status: 'resolved', option_ids: ids,
    intents: ids.map(id => ({ expression: id, candidate_option_ids: [id] })), unresolved: [] };
}
