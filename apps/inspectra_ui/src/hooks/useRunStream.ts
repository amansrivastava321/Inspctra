import { useState, useEffect, useRef, useCallback } from 'react';
import { createRunStream } from '../api/client';
import type { RunEvent } from '../types/api';

interface UseRunStreamState {
  events: RunEvent[];
  connected: boolean;
  error: string | null;
  terminal: boolean;
}

export function useRunStream(runId: string | null, active = true) {
  const [state, setState] = useState<UseRunStreamState>({
    events: [],
    connected: false,
    error: null,
    terminal: false,
  });
  const esRef = useRef<EventSource | null>(null);
  const MAX_EVENTS = 500;

  const addEvent = useCallback((ev: RunEvent) => {
    setState(s => ({
      ...s,
      events: [...s.events.slice(-MAX_EVENTS + 1), ev],
    }));
  }, []);

  useEffect(() => {
    if (!runId || !active) return;

    const es = createRunStream(runId);
    esRef.current = es;
    setState(s => ({ ...s, terminal: false }));

    es.onopen = () => setState(s => ({ ...s, connected: true, error: null }));
    es.onerror = () => setState(s => ({ ...s, connected: false, error: 'Stream disconnected' }));

    const handler = (raw: MessageEvent) => {
      try {
        const payload = JSON.parse(raw.data as string) as Record<string, unknown>;
        const eventType = raw.type || 'message';
        if (
          eventType === 'done'
          || (eventType === 'status' && ['completed', 'failed', 'cancelled'].includes(String(payload.status)))
        ) {
          setState(s => ({ ...s, connected: false, terminal: true }));
          es.close();
          return;
        }
        if (eventType === 'connected' || eventType === 'status') return;
        const ev = { ...payload, type: eventType } as unknown as RunEvent;
        addEvent(ev);
      } catch {
        // skip malformed
      }
    };

    es.addEventListener('message', handler);
    // Named event types
    ['step_start','step_end','screenshot','log','api_call','db_delta',
     'ai_oracle','permission_request','verdict','heartbeat','error',
     'connected','status','done'].forEach(t => {
      es.addEventListener(t, handler);
    });

    return () => {
      es.close();
      esRef.current = null;
      setState(s => ({ ...s, connected: false }));
    };
  }, [runId, active, addEvent]);

  const clear = useCallback(() => setState(s => ({ ...s, events: [] })), []);

  return { ...state, clear };
}
