import { useEffect, useMemo, useRef, useState } from 'react';
import { ChevronDown, ChevronUp, Wifi, WifiOff } from 'lucide-react';
import { F, P } from '../../design/tokens';
import type { DurableRunEvent, RunEvent } from '../../types/api';

const EVENT_COLOR: Record<string, string> = {
  step_started: P.accent,
  step_start: P.accent,
  step_completed: P.pass,
  step_end: P.pass,
  evidence_captured: P.textDim,
  screenshot: P.textDim,
  log: P.textMute,
  api_call: P.unclear,
  db_delta: P.unclear,
  ai_oracle: P.accent,
  permission_request: P.fail,
  verdict: P.pass,
  error: P.fail,
  heartbeat: P.textFaint,
};

interface EventStreamDrawerProps {
  durableEvents?: DurableRunEvent[];
  liveEvents?: RunEvent[];
  /** Backward-compatible alias while callers migrate to liveEvents. */
  events?: RunEvent[];
  connected: boolean;
  active?: boolean;
  error?: string | null;
  defaultOpen?: boolean;
}

interface DisplayEvent {
  key: string;
  type: string;
  timestamp: string;
  message: string;
  confidence?: number;
}

function liveEventType(event: RunEvent): string {
  if (event.type === 'step_start') return 'step_started';
  if (event.type === 'step_end') return 'step_completed';
  if (event.type === 'screenshot' || (event.type === 'log' && event.evidence_id)) {
    return 'evidence_captured';
  }
  return event.type;
}

function eventIdentity(
  type: string,
  timestamp: string,
  stepId?: unknown,
  stepIndex?: unknown,
  evidenceId?: unknown,
): string {
  return [type, timestamp, stepId ?? '', stepIndex ?? '', evidenceId ?? ''].join('|');
}

export function EventStreamDrawer({
  durableEvents = [],
  liveEvents,
  events,
  connected,
  active = false,
  error,
  defaultOpen = false,
}: EventStreamDrawerProps) {
  const [open, setOpen] = useState(defaultOpen);
  const listRef = useRef<HTMLDivElement>(null);
  const live = liveEvents ?? events ?? [];
  const merged = useMemo(() => {
    const result: DisplayEvent[] = durableEvents.map((event) => ({
      key: `durable-${event.id}`,
      type: event.event_type,
      timestamp: event.created_at,
      message: event.message,
    }));
    const signatures = new Set(durableEvents.map((event) => eventIdentity(
      event.event_type,
      event.created_at,
      event.step_id,
      event.step_index ?? event.payload.step,
      event.payload.evidence_id,
    )));
    live.forEach((event, index) => {
      const type = liveEventType(event);
      if (type === 'step_started' && event.step == null && event.step_id == null) return;
      const message = event.message
        ?? (type === 'step_started' ? `Step ${event.step ?? ''} started: ${event.step_name ?? 'Unnamed step'}` : undefined)
        ?? (type === 'step_completed' ? `Step ${event.step ?? ''} completed: ${event.status ?? 'unknown'}` : undefined)
        ?? (type === 'evidence_captured' ? 'Evidence captured' : undefined)
        ?? event.step_name
        ?? '';
      const signature = eventIdentity(type, event.ts, event.step_id, event.step, event.evidence_id);
      if (signatures.has(signature)) return;
      signatures.add(signature);
      result.push({
        key: `live-${index}-${signature}`,
        type,
        timestamp: event.ts,
        message,
        confidence: event.confidence,
      });
    });
    return result.sort((left, right) => left.timestamp.localeCompare(right.timestamp));
  }, [durableEvents, live]);

  useEffect(() => {
    if (open && listRef.current) {
      // Keep history movement inside the bounded list. scrollIntoView here
      // also moves the surrounding investigation workspace and hides evidence.
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [merged.length, open]);

  return (
    <div style={{ borderTop: `1px solid ${P.border}`, background: P.surface, flexShrink: 0 }}>
      <button type="button" onClick={() => setOpen((value) => !value)} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: 8, padding: '8px 16px', background: 'none', cursor: 'pointer', border: 0, borderBottom: open ? `1px solid ${P.border}` : 'none' }}>
        {connected ? <Wifi size={12} color={P.pass} /> : <WifiOff size={12} color={active ? P.fail : P.textFaint} />}
        <span style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono }}>EVENT HISTORY</span>
        <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono }}>{merged.length} events</span>
        {error && <span style={{ fontSize: 10, color: P.fail }}>{error}</span>}
        <span style={{ marginLeft: 'auto', color: P.textFaint }}>{open ? <ChevronDown size={13} /> : <ChevronUp size={13} />}</span>
      </button>
      {open && (
        <div ref={listRef} style={{ maxHeight: 220, overflowY: 'auto', padding: '7px 0' }}>
          {merged.length === 0 ? (
            <div style={{ padding: '16px 20px', fontSize: 12, color: P.textMute }}>
              {active || connected
                ? 'Waiting for events…'
                : 'No event stream available for this run. Event capture was enabled on 14 August 2026.'}
            </div>
          ) : merged.map((event) => (
            <div key={event.key} style={{ display: 'flex', gap: 10, padding: '4px 16px', alignItems: 'baseline' }}>
              <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono, flexShrink: 0, width: 76 }}>{new Date(event.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
              <span style={{ fontSize: 10, fontFamily: F.mono, color: EVENT_COLOR[event.type] ?? P.textMute, flexShrink: 0, width: 122 }}>{event.type.replace(/_/g, ' ').toUpperCase()}</span>
              <span style={{ fontSize: 11, color: P.textDim, flex: 1, minWidth: 0 }}>{event.message}</span>
              {event.confidence !== undefined && <span style={{ fontSize: 10, color: P.textFaint, fontFamily: F.mono }}>{event.confidence}%</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
