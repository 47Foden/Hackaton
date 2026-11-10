import type { Menu, Temperature } from '../../data/menuCatalog';
import { temperatureLabels } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

export function TemperatureScreen({ menu, onSelect, quantity = 1 }: { quantity?: number; menu: Menu; onSelect: (value: Temperature) => void }) {
  return (
    <section className="order-step" aria-label="온도 선택">
      <OrderSummary quantity={quantity} menu={menu} />
      <div className="order-choices">
        {menu.temperatures.map(temperature => (
          <button key={temperature} type="button" className="order-choice" onClick={() => onSelect(temperature)}>
            <span className="order-choice__code">{temperature === 'HOT' ? 'HOT' : 'ICE'}</span>
            {temperatureLabels[temperature]}
          </button>
        ))}
      </div>
    </section>
  );
}
