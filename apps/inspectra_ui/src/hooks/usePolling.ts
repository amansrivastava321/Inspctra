import { useEffect, useRef } from 'react';

export function usePolling(fn: () => void | Promise<void>, intervalMs: number, active = true) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    if (!active) return;
    const t = setInterval(() => { void fnRef.current(); }, intervalMs);
    return () => clearInterval(t);
  }, [intervalMs, active]);
}
