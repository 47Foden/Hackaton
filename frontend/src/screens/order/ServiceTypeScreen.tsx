import type { Menu, Temperature } from '../../data/menuCatalog';
import { serviceTypeLabels, type ServiceType } from '../../state/order';
import { OrderSummary } from '../../components/order/OrderSummary';

export function ServiceTypeScreen({ menu, temperature, onSelect }: {
  menu: Menu; temperature: Temperature; onSelect: (value: ServiceType) => void;
}) {
  return (
    <section className="order-step" aria-label="매장 또는 포장 선택">
      <OrderSummary menu={menu} temperature={temperature} />
      {menu.temperatures.length === 1 && <p className="order-step__note">이 메뉴는 {temperature === 'COLD' ? '차가운' : '따뜻한'} 음료로 제공돼요.</p>}
      <div className="order-choices">
        {(['DINE_IN', 'TAKEOUT'] as const).map(serviceType => (
          <button type="button" key={serviceType} className="order-choice" onClick={() => onSelect(serviceType)}>
            {serviceTypeLabels[serviceType]}<span className="order-choice__hint">{serviceType === 'DINE_IN' ? '먹고 갈게요' : '가져갈게요'}</span>
          </button>
        ))}
      </div>
    </section>
  );
}
