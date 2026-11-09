import type { MenuOption, MenuOptionGroup } from '../api/contracts.ts';

export function resolveOrderOptions(groups: MenuOptionGroup[], ids: string[]): MenuOption[] | null {
  const requested = new Set(ids);
  if (requested.size !== ids.length) return null;
  const selected = [];
  for (const group of groups) {
    const choices = group.choices.filter(choice => requested.has(choice.id));
    if (choices.length > group.max_selections) return null;
    selected.push(...choices);
  }
  return selected.length === requested.size ? selected : null;
}
