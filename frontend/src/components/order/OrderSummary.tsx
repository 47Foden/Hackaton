import type { Menu, Temperature } from '../../data/menuCatalog';
import { serviceTypeLabels, temperatureLabels, type ServiceType } from '../../state/order';
import { MenuImage } from '../menu/MenuImage';

interface OrderSummaryProps { menu: Menu; temperature?: Temperature; serviceType?: ServiceType; }

export function OrderSummary({ menu, temperature, serviceType }: OrderSummaryProps) {
  const imageUrl = (temperature && menu.imageUrls[temperature]) || menu.imageUrl;
  return (
    <div className="order-summary">
      <MenuImage src={imageUrl} />
      <div>
        <h2>{menu.name}</h2>
        <p>{menu.price.toLocaleString('ko-KR')}원 · 1잔</p>
        {(temperature || serviceType) && <p className="order-summary__options">
          {temperature && temperatureLabels[temperature]}
          {temperature && serviceType && ' · '}
          {serviceType && serviceTypeLabels[serviceType]}
        </p>}
      </div>
    </div>
  );
}
