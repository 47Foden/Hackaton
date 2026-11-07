import type { Menu, Temperature } from '../../data/menuCatalog';
import { serviceTypeLabels, temperatureLabels, type ServiceType } from '../../state/order';
import { useState } from 'react';

interface OrderSummaryProps { menu: Menu; temperature?: Temperature; serviceType?: ServiceType; }

export function OrderSummary({ menu, temperature, serviceType }: OrderSummaryProps) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageUrl = (temperature && menu.imageUrls[temperature]) || menu.imageUrl;
  return (
    <div className="order-summary">
      {!imageFailed && <img src={imageUrl} alt="" onError={() => setImageFailed(true)} />}
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
