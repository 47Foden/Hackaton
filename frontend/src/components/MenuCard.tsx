import { useState } from 'react';
import type { Menu } from '../data/menuCatalog';

interface MenuCardProps { menu: Menu; selected: boolean; onSelect: () => void; }

export function MenuCard({ menu, selected, onSelect }: MenuCardProps) {
  const [imageFailed, setImageFailed] = useState(false);
  return (
    <button type="button" className={`menu-card${selected ? ' menu-card--selected' : ''}`}
      aria-pressed={selected} onClick={onSelect}>
      <span className="menu-card__temperature">{menu.temperatures.join(' / ')}</span>
      {imageFailed
        ? <span className="menu-card__image menu-card__placeholder">사진 준비 중</span>
        : <img className="menu-card__image" src={menu.imageUrl} alt="" onError={() => setImageFailed(true)} />}
      <span className="menu-card__name">{menu.name}</span>
      <span className="menu-card__price">{menu.price.toLocaleString('ko-KR')}원</span>
      {selected && <span className="menu-card__selected">✓ 선택한 메뉴</span>}
    </button>
  );
}
