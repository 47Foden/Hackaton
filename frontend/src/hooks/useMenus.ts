import { useEffect, useState } from 'react';
import type { KioskApi } from '../api/contracts';
import { asApiError } from '../api/errors';
import { toMenu, type Menu } from '../data/menuCatalog';

type MenuLoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; menus: Menu[] };

export function useMenus(api: KioskApi) {
  const [state, setState] = useState<MenuLoadState>({ status: 'loading' });
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setState({ status: 'loading' });
    api.getMenus(controller.signal).then(response => {
      if (!controller.signal.aborted) setState({ status: 'ready', menus: response.menus.map(toMenu) });
    }).catch(error => {
      if (!controller.signal.aborted) setState({ status: 'error', message: asApiError(error).message });
    });
    return () => controller.abort();
  }, [api, attempt]);
  return { state, reload: () => {
    setState({ status: 'loading' });
    setAttempt(value => value + 1);
  } };
}
