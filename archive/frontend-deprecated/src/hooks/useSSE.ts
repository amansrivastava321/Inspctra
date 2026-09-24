/**
 * useSSE — subscribes to an SSE endpoint and returns accumulated events.
 * Automatically reconnects on connection loss.
 * Closes connection when component unmounts or runId changes.
 */
import { useState, useEffect, useRef } from 'react';

export interface SSEEvent {
  type: string;
  data: unknown;
  receivedAt: string;
}

interface SSEState {
  events: SSEEvent[];
  connected: boolean;
  done: boolean;
}

export function useSSE(runId: string | null): SSEState {
  const [state, setState] = useState<SSEState>({ events: [], connected: false, done: false });
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!runId) return;

    setState({ events: [], connected: false, done: false });

    const url = `/api/runs/${runId}/stream`;
    const es = new EventSource(url);
    esRef.current = es;

    const addEvent = (type: string, raw: string) => {
      try {
        const data = JSON.parse(raw);
        setState(prev => ({
          ...prev,
          events: [...prev.events, { type, data, receivedAt: new Date().toISOString() }],
        }));
      } catch { /* malformed event — ignore */ }
    };

    es.addEventListener('connected', e => {
      setState(prev => ({ ...prev, connected: true }));
      addEvent('connected', (e as MessageEvent).data);
    });

    es.addEventListener('status', e => {
      addEvent('status', (e as MessageEvent).data);
    });

    es.addEventListener('step_start', e => {
      addEvent('step_start', (e as MessageEvent).data);
    });

    es.addEventListener('step_result', e => {
      addEvent('step_result', (e as MessageEvent).data);
    });

    es.addEventListener('error', e => {
      addEvent('error', (e as MessageEvent).data || '{}');
    });

    es.addEventListener('done', e => {
      addEvent('done', (e as MessageEvent).data);
      setState(prev => ({ ...prev, done: true, connected: false }));
      es.close();
    });

    es.onerror = () => {
      setState(prev => ({ ...prev, connected: false }));
      // EventSource auto-reconnects; close if already done
      if (state.done) es.close();
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId]);

  return state;
}
