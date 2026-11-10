import type { ReactNode } from 'react';
import type { Menu, Temperature } from '../../data/menuCatalog';
import type { MenuOption } from '../../api/contracts';
import { serviceTypeLabels, temperatureLabels, type ServiceType } from '../../state/order';
import { MenuImage } from '../menu/MenuImage';

interface OrderSummaryProps { menu: Menu; temperature?: Temperature; serviceType?: ServiceType; selectedOptions?: MenuOption[]; quantity?: number; action?: ReactNode; }

export function OrderSummary({ menu, temperature, serviceType, selectedOptions = [], quantity = 1, action }: OrderSummaryProps) {
  const imageUrl = (temperature && menu.imageUrls[temperature]) || menu.imageUrl;
  return (
    <div className="order-summary">
      <MenuImage src={imageUrl} />
      <div>
        <h2>{menu.name}</h2>
        <p>{menu.price.toLocaleString('ko-KR')}원 · {quantity}잔</p>
        {(temperature || serviceType) && <p className="order-summary__options">
          {temperature && temperatureLabels[temperature]}
          {temperature && serviceType && ' · '}
          {serviceType && serviceTypeLabels[serviceType]}
        </p>}
        {selectedOptions.length > 0 && <ul className="order-summary__selections">
          {selectedOptions.map(option => <li key={option.id}>
            {option.label} · {option.price_delta_krw ? '+' : ''}{option.price_delta_krw.toLocaleString('ko-KR')}원
          </li>)}
        </ul>}
      </div>
      {action}
    </div>
  );
}
