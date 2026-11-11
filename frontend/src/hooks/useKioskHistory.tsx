import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';

type Screen = 'start' | 'order' | 'voice';
type Entry = { token: string; position: number; screen: Screen; session: string; step?: string; snapshot?: unknown };
type Handler = { restore: (snapshot: unknown) => void; locked: () => boolean; complete: () => boolean };
type Navigation = {
  current: () => Entry;
  navigate: (screen: Screen) => void;
  home: () => void;
  register: (handler: Handler) => () => void;
  record: (step: string, snapshot: unknown, replace: boolean) => void;
};
const Context = createContext<Navigation | null>(null);
const STATE_KEY = 'kioskNavigation';

export function KioskHistory({ children }: { children: (screen: Screen, session: string) => ReactNode }) {
  const token = useRef(crypto.randomUUID());
  const initial = useRef<Entry>({ token: token.current, position: 0, screen: 'start', session: crypto.randomUUID() });
  const current = useRef(initial.current);
  const handler = useRef<Handler | null>(null);
  const closed = useRef(new Set<string>());
  const [location, setLocation] = useState(initial.current);
  const [notice, setNotice] = useState('');
  function write(entry: Entry, replace: boolean) {
    window.history[replace ? 'replaceState' : 'pushState']({ ...window.history.state, [STATE_KEY]: entry }, '');
    current.current = entry;
  }
  const navigation = useMemo<Navigation>(() => ({
    current: () => current.current,
    navigate(screen) {
      const entry: Entry = { token: token.current, position: current.current.position + 1,
        screen, session: crypto.randomUUID() };
      write(entry, false); setNotice(''); setLocation(entry);
    },
    home() {
      closed.current.add(current.current.session);
      navigation.navigate('start');
    },
    register(next) {
      handler.current = next;
      return () => { if (handler.current === next) handler.current = null; };
    },
    record(step, snapshot, replace) {
      const previous = current.current;
      const push = previous.step !== undefined && previous.step !== step && !replace;
      write({ ...previous, position: previous.position + (push ? 1 : 0), step, snapshot }, !push);
    },
  }), []);

  useLayoutEffect(() => { write(initial.current, true); }, []);
  useEffect(() => {
    function pop(event: PopStateEvent) {
      let target = event.state?.[STATE_KEY] as Entry | undefined;
      if (!target || target.token !== token.current) return;
      const previous = current.current;
      if (handler.current?.locked() && !handler.current.complete()) {
        // Preserve the request ID and draft while submission/recovery is pending.
        const distance = previous.position - target.position;
        if (distance) window.history.go(distance);
        setNotice('주문 접수 결과를 확인한 뒤 이동해 주세요.');
        return;
      }
      if (handler.current?.complete()) closed.current.add(previous.session);
      if (closed.current.has(target.session)) {
        target = { token: token.current, position: target.position, screen: 'start', session: crypto.randomUUID() };
        write(target, true);
      } else current.current = target;
      setNotice('');
      if (target.session === previous.session && target.snapshot !== undefined) handler.current?.restore(target.snapshot);
      setLocation(target);
    }
    window.addEventListener('popstate', pop);
    return () => window.removeEventListener('popstate', pop);
  }, []);

  return <Context.Provider value={navigation}>
    {notice && <p role="status">{notice}</p>}
    {children(location.screen, location.session)}
  </Context.Provider>;
}

export function useKioskNavigation() {
  const value = useContext(Context);
  if (!value) throw new Error('KioskHistory provider is required');
  return value;
}

// Keep snapshots only in this tab's session history; no storage or API calls.
export function useKioskStep<T>(step: string, snapshot: T, restore: (snapshot: T) => void,
                               locked: boolean, complete: boolean) {
  const navigation = useKioskNavigation();
  const latest = useRef({ restore, locked, complete });
  latest.current = { restore, locked, complete };
  const restoring = useRef(false);
  useLayoutEffect(() => {
    const saved = navigation.current().snapshot;
    if (saved !== undefined) {
      restoring.current = true;
      latest.current.restore(saved as T);
    }
    return navigation.register({
      restore: value => latest.current.restore(value as T),
      locked: () => latest.current.locked,
      complete: () => latest.current.complete,
    });
  }, [navigation]);
  useLayoutEffect(() => {
    if (restoring.current) { restoring.current = false; return; }
    navigation.record(step, snapshot, locked || complete);
  });
}
