import { useId, useState } from 'react';
import { MenuCard } from '../MenuCard';
import type { Menu } from '../../data/menuCatalog';
import './MenuBoard.css';
import { menuCategories, matchesCategory } from '../../data/menuCategories';

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
  const [category, setCategory] = useState('커피');
  const [subcategory, setSubcategory] = useState('에스프레소');
  const headingId = useId();
  const gridId = useId();
  const showAll = view.mode === 'all' || simplifiedMenus.length === 0;
  const visibleMenus = showAll
    ? (groupByCategory ? menus.filter(menu => matchesCategory(menu, category, subcategory)) : menus)
    : simplifiedMenus;
  const selectedOutsideList = selectedMenu !== null
    && !visibleMenus.some(menu => menu.name === selectedMenu);

  function selectCategory(next: string) {
    setCategory(next);
    setSubcategory(menuCategories[next][0]);
    onViewChange({ ...view, mode: 'all' });
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
      {groupByCategory && <div className="menu-board__navigation">
        <div className="menu-board__tabs" role="group" aria-label="음료 대분류">
          {Object.keys(menuCategories).map(item => <button key={item} type="button"
            aria-pressed={showAll && category === item}
            onClick={() => selectCategory(item)}>{item}</button>)}
        </div>
        <div className="menu-board__chips" role="group" aria-label={`${category} 세부 분류`}>
          {menuCategories[category].map(item => <button key={item} type="button"
            aria-pressed={showAll && subcategory === item}
            onClick={() => { setSubcategory(item); onViewChange({ ...view, mode: 'all' }); }}>{item}</button>)}
        </div>
      </div>}
      <p className="menu-board__summary" role="status">
        총 <strong>{visibleMenus.length}</strong>개
        <span> · {showAll && groupByCategory ? `${category} / ${subcategory}` : showAll ? '전체 메뉴' : '간편 메뉴'}
          {view.enlarged && ' · 확대 크기'}</span>
        {selectedOutsideList && ` · 선택한 ${selectedMenu} 메뉴는 다른 분류에 있어요.`}
      </p>
      <div id={gridId} className="menu-grid">
        {visibleMenus.map(menu => <MenuCard key={menu.id} menu={menu} selected={selectedMenu === menu.name}
          onSelect={() => onSelect(menu.id)} />)}
        {visibleMenus.length === 0 && <p className="menu-board__empty">이 분류에 등록된 메뉴가 없어요. 다른 분류를 선택해 주세요.</p>}
      </div>
    </section>
  );
}
