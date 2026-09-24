import { useState, useEffect, useCallback, useRef } from 'react';
import { ApiError, checkHealth } from '../api/client';
import { useWorkspaceMode } from '../state/WorkspaceModeContext';
import type { DemoWorkspace } from '../mocks/sampleData';

interface UseApiState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** Compatibility alias for demo mode. */
  isMock: boolean;
  isDemo: boolean;
  /** true when backend is unreachable — never silently falls back */
  isOffline: boolean;
  /** When data was last successfully fetched; null until first success. */
  fetchedAt: Date | null;
}

function resolveDemoValue<T>(
  workspace: DemoWorkspace | null,
  demo: T | ((workspace: DemoWorkspace) => T) | undefined,
): T | null {
  if (!workspace || demo === undefined) return null;
  return typeof demo === 'function'
    ? (demo as (workspace: DemoWorkspace) => T)(workspace)
    : demo;
}

export function useApi<T>(
  fn: () => Promise<T>,
  opts?: { skip?: boolean; demo?: T | ((workspace: DemoWorkspace) => T) }
) {
  const { isDemo, demoWorkspace } = useWorkspaceMode();
  const [state, setState] = useState<UseApiState<T>>(() => {
    const demoValue = isDemo ? resolveDemoValue(demoWorkspace, opts?.demo) : null;
    return {
      data: demoValue,
      loading: !isDemo,
      error: isDemo && demoValue === null ? 'No sample data is available for this view.' : null,
      isMock: isDemo,
      isDemo,
      isOffline: false,
      fetchedAt: isDemo ? new Date() : null,
    };
  });
  const mounted = useRef(true);

  const execute = useCallback(async () => {
    if (opts?.skip) {
      setState(s => ({ ...s, loading: false }));
      return;
    }
    if (isDemo) {
      const demoValue = resolveDemoValue(demoWorkspace, opts?.demo);
      setState({
        data: demoValue,
        loading: false,
        error: demoValue === null ? 'No sample data is available for this view.' : null,
        isMock: true,
        isDemo: true,
        isOffline: false,
        fetchedAt: new Date(),
      });
      return;
    }
    setState(s => ({ ...s, loading: true, error: null, isMock: false, isDemo: false, isOffline: false }));
    try {
      const data = await fn();
      if (mounted.current) {
        setState({ data: data ?? null, loading: false, error: null, isMock: false, isDemo: false, isOffline: false, fetchedAt: new Date() });
      }
    } catch (err) {
      if (!mounted.current) return;

      if (err instanceof ApiError && err.status === 0) {
        setState({ data: null, loading: false, error: 'Backend offline', isMock: false, isDemo: false, isOffline: true, fetchedAt: null });
        return;
      }

      if (err instanceof ApiError && err.status >= 500) {
        const health = await checkHealth();
        if (!mounted.current) return;
        if (health === 'offline') {
          setState({ data: null, loading: false, error: 'Backend offline', isMock: false, isDemo: false, isOffline: true, fetchedAt: null });
          return;
        }
      }

      // API error (4xx, 5xx, timeout) — show error, no fallback
      const msg = err instanceof ApiError ? err.message : String(err);
      setState({ data: null, loading: false, error: msg, isMock: false, isDemo: false, isOffline: false, fetchedAt: null });
    }
  }, [demoWorkspace, fn, isDemo, opts?.skip]);

  useEffect(() => {
    mounted.current = true;
    execute();
    return () => { mounted.current = false; };
  }, [execute]);

  return { ...state, refetch: execute };
}

export function useApiPolling<T>(fn: () => Promise<T>, intervalMs = 5000, opts?: { demo?: T | ((workspace: DemoWorkspace) => T) }) {
  const result = useApi(fn, opts);
  useEffect(() => {
    if (result.isDemo) return;
    const t = setInterval(() => result.refetch(), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs, result.isDemo, result.refetch]);
  return result;
}
