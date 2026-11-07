import './CatalogStatus.css';

type CatalogStatusProps =
  | { status: 'loading' }
  | { status: 'error'; message: string; onReload: () => void }
  | { status: 'empty'; onReload: () => void };

export function CatalogStatus(props: CatalogStatusProps) {
  const loading = props.status === 'loading';
  return (
    <section className="catalog-status" role={props.status === 'error' ? 'alert' : 'status'} aria-busy={loading}>
      <h2>{loading ? '메뉴를 불러오는 중이에요…' : props.status === 'error' ? '메뉴를 불러오지 못했어요.' : '표시할 메뉴가 없어요.'}</h2>
      <p>{loading ? '잠시만 기다려 주세요.' : props.status === 'error' ? props.message : '잠시 후 메뉴를 다시 불러와 주세요.'}</p>
      {!loading && <button type="button" className="outline-button" onClick={props.onReload}>다시 불러오기</button>}
    </section>
  );
}
