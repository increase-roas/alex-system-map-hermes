'use client';

import { useEffect, useRef } from 'react';

/** Calls fn once on open, then every `ms` while the tab is visible; catches up when the tab comes back. */
export function usePoll(fn: () => void | Promise<void>, ms: number) {
  const latest = useRef(fn);
  latest.current = fn;
  useEffect(() => {
    let last = 0;
    const run = () => {
      last = Date.now();
      void latest.current();
    };
    const tick = () => {
      if (document.visibilityState === 'visible') run();
    };
    run(); // always load once on open, even in a background tab; repeats pause while hidden
    const id = window.setInterval(tick, ms);
    const onVisible = () => {
      if (document.visibilityState === 'visible' && Date.now() - last >= ms) tick();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      window.clearInterval(id);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [ms]);
}
