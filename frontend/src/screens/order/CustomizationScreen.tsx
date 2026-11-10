import { useState } from 'react';
import type { MenuOptionGroup } from '../../api/contracts';
import { OrderSummary } from '../../components/order/OrderSummary';
import type { Menu, Temperature } from '../../data/menuCatalog';
import { resolveOrderOptions } from '../../state/orderOptions';

export function CustomizationScreen({ menu, temperature, onContinue, initialSelectedIds = [], onSelectionChange }: {
  menu: Menu; temperature: Temperature; onContinue: (ids: string[]) => void;
  initialSelectedIds?: string[]; onSelectionChange?: (ids: string[]) => void;
}) {
  const groups = menu.optionGroups[temperature] ?? [];
  const [selectedIds, setSelectedIds] = useState<string[]>(initialSelectedIds);
  const selected = resolveOrderOptions(groups, selectedIds) ?? [];
  const total = menu.price + selected.reduce((sum, choice) => sum + choice.price_delta_krw, 0);

  function toggle(group: MenuOptionGroup, id: string) {
    const next = ((ids: string[]) => {
      if (ids.includes(id)) return ids.filter(value => value !== id);
      const inGroup = (value: string) => group.choices.some(choice => choice.id === value);
      if (group.max_selections === 1) return [...ids.filter(value => !inGroup(value)), id];
      return ids.filter(inGroup).length < group.max_selections ? [...ids, id] : ids;
    })(selectedIds);
    setSelectedIds(next); onSelectionChange?.(next);
  }

  return (
    <section className="order-step" aria-label="추가 옵션 선택">
      <OrderSummary menu={menu} temperature={temperature} />
      {groups.map(group => (
        <fieldset className="customization-group" key={group.id}>
          <legend>{group.label}</legend>
          <div className="customization-choices">
            {group.choices.map(choice => (
              <button type="button" className="outline-button customization-choice" key={choice.id}
                aria-pressed={selectedIds.includes(choice.id)} onClick={() => toggle(group, choice.id)}>
                <span>{choice.label}</span>
                <span>{choice.price_delta_krw ? '+' : ''}{choice.price_delta_krw.toLocaleString('ko-KR')}원</span>
              </button>
            ))}
          </div>
        </fieldset>
      ))}
      <p className="order-step__total" aria-live="polite">합계 <strong>{total.toLocaleString('ko-KR')}원</strong></p>
      <button type="button" className="primary-button order-step__confirm" onClick={() => onContinue(selectedIds)}>
        {selectedIds.length ? '선택한 옵션으로 계속' : '옵션 없이 계속'}
      </button>
    </section>
  );
}
