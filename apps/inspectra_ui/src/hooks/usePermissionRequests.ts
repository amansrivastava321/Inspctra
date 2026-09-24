import { useState, useEffect, useCallback } from 'react';
import type { PermissionRecord } from '../types/api';
import { get, post } from '../api/client';
import { useWorkspaceMode } from '../state/WorkspaceModeContext';

export function usePermissionRequests(runId?: string, pollMs = 3000) {
  const { isDemo } = useWorkspaceMode();
  const [pending, setPending] = useState<PermissionRecord[]>([]);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    try {
      setLoading(true);
      const qs = new URLSearchParams({ status: 'pending' });
      if (runId) qs.set('run_id', runId);
      const data = await get<PermissionRecord[]>(`/permissions?${qs}`);
      setPending(data);
    } catch {
      // fail silently — permissions are supplementary
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    if (isDemo || !runId || pollMs <= 0) return;
    fetch();
    const t = setInterval(fetch, pollMs);
    return () => clearInterval(t);
  }, [fetch, isDemo, pollMs, runId]);

  const approve = useCallback(async (id: string, reason?: string) => {
    await post(`/permissions/${encodeURIComponent(id)}/approve`, { approved: true, reason });
    setPending(ps => ps.filter(p => p.id !== id));
  }, []);

  const deny = useCallback(async (id: string, reason?: string) => {
    await post(`/permissions/${encodeURIComponent(id)}/deny`, { approved: false, reason });
    setPending(ps => ps.filter(p => p.id !== id));
  }, []);

  return { pending, loading, approve, deny, refresh: fetch };
}
