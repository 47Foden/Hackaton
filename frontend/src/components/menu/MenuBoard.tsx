import { useId } from 'react';
import { MenuCard } from '../MenuCard';
import type { Menu } from '../../data/menuCatalog';
import './MenuBoard.css';

export interface MenuBoardView {
  mode: 'simplified' | 'all';
  enlarged: boolean;
}

interface MenuBoardProps {
  menus: Menu[];
  simplifiedMenus: Menu[];
  groupByCategory?: boolean;
  selectedMenu: string | null;
  view: MenuBoardView;
  onViewChange: (view: MenuBoardView) => void;
  onSelect: (menuId: string) => void;
}

/** 목록 전환과 확대는 서로 독립적이며, 상태는 주문 화면이 유지한다. */
export function MenuBoard({
  menus, simplifiedMenus, groupByCategory = false, selectedMenu, view, onViewChange, onSelect,
}: MenuBoardProps) {
  const headingId = useId();
  const gridId = useId();
  const showAll = view.mode === 'all' || simplifiedMenus.length === 0;
  const visibleMenus = showAll ? menus : simplifiedMenus;
  const selectedOutsideList = selectedMenu !== null
    && !visibleMenus.some(menu => menu.name === selectedMenu);
  const groups = new Map<string, Menu[]>();
  for (const menu of visibleMenus) {
    const category = showAll && groupByCategory ? menu.categories.join(' · ') : '';
    const group = groups.get(category);
    if (group) group.push(menu);
    else groups.set(category, [menu]);
  }

  return (
    <section className={`menu-board${view.enlarged ? ' menu-board--enlarged' : ''}`}
      aria-labelledby={headingId}>
      <div className="menu-board__heading">
        <div>
          <span className="eyebrow">MEGA MENU</span>
          <h2 id={headingId}>{showAll ? '전체 메뉴판' : '간편 메뉴판'}</h2>
        </div>
        <div className="menu-board__controls">
          {simplifiedMenus.length > 0 && (
            <button type="button" className="outline-button" aria-controls={gridId}
              aria-expanded={showAll}
              onClick={() => onViewChange({ ...view, mode: showAll ? 'simplified' : 'all' })}>
              {showAll ? '간편 메뉴판 보기' : '전체 메뉴판 보기'}
            </button>
          )}
          <button type="button" className="outline-button" aria-controls={gridId}
            aria-pressed={view.enlarged}
            onClick={() => onViewChange({ ...view, enlarged: !view.enlarged })}>
            {view.enlarged ? '기본 크기로 보기' : '크게 보기'}
          </button>
        </div>
      </div>
      <p className="menu-board__summary" role="status">
        {visibleMenus.length}종 표시 · {view.enlarged ? '확대 크기' : '기본 크기'}
        {selectedOutsideList && ` · 선택한 ${selectedMenu} 메뉴는 전체 메뉴판에서 확인할 수 있어요.`}
      </p>
      <div id={gridId}>
        {[...groups].map(([category, group]) => (
          <section key={category} className="menu-board__category">
            {category && <h3>{category}</h3>}
            <div className="menu-grid">
              {group.map(menu => <MenuCard key={menu.id} menu={menu} selected={selectedMenu === menu.name}
                onSelect={() => onSelect(menu.id)} />)}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}
