import { MenuImage } from './menu/MenuImage';
import type { Menu } from '../data/menuCatalog';

interface MenuCardProps { menu: Menu; selected: boolean; onSelect: () => void; }

export function MenuCard({ menu, selected, onSelect }: MenuCardProps) {
  return (
    <button type="button" className={`menu-card${selected ? ' menu-card--selected' : ''}`}
      aria-pressed={selected} disabled={!menu.available} onClick={onSelect}>
      <span className="menu-card__temperature">{menu.temperatures.join(' / ')}</span>
      <MenuImage className="menu-card__image" src={menu.imageUrl} />
      <span className="menu-card__name">{menu.name}</span>
      <span className="menu-card__price">{menu.price.toLocaleString('ko-KR')}원</span>
      {!menu.available && <span>판매 중지</span>}
      {selected && <span className="menu-card__selected">✓ 선택한 메뉴</span>}
    </button>
  );
}
