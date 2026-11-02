import { useState } from 'react';
import { P, F } from '../../design/tokens';
import { Btn, Card } from '../layout/AppShell';
import { patch } from '../../api/client';
import {
  INTERVAL_LIMITS,
  buildSchedule,
  describeSchedule,
  isNotScheduled,
  parseSchedule,
  validateInterval,
  type ScheduleKind,
} from '../../config/schedule';

export interface SchedulablePack {
  id: string;
  schedule?: string;
  schedule_enabled?: boolean;
  schedule_timezone?: string;
  continuous?: boolean;
  notify_webhook_url?: string | null; // the API only returns the origin of a saved URL
  next_run_at?: string | null;
  last_scheduled_run_at?: string | null;
}

const KIND_LABEL: Record<ScheduleKind, string> = {
  none: 'Off (run by hand only)',
  minutes: 'Every N minutes',
  hours: 'Every N hours',
  hourly: 'Every hour',
  daily: 'Every day at 02:00',
  weekdays: 'Weekdays at 09:00',
};

const LABEL: React.CSSProperties = {
  fontSize: 11, color: P.textMute, fontFamily: F.mono, textTransform: 'uppercase', letterSpacing: '0.06em',
};
const INPUT: React.CSSProperties = {
  padding: '6px 8px', borderRadius: 6, border: `1px solid ${P.border}`, background: P.cardHi,
  color: P.text, fontSize: 13, fontFamily: F.ui,
};

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

function knownTimezones(): string[] {
  try {
    const supported = (Intl as unknown as { supportedValuesOf?: (key: string) => string[] }).supportedValuesOf;
    return supported ? supported('timeZone') : [];
  } catch {
    return [];
  }
}

export function SchedulePanel({ pack, onSaved }: { pack: SchedulablePack; onSaved: () => void }) {
  const initial = parseSchedule(pack.schedule);
  const [kind, setKind] = useState<ScheduleKind>(initial.kind);
  const [every, setEvery] = useState<number>(initial.every);
  const [enabled, setEnabled] = useState<boolean>(Boolean(pack.schedule_enabled));
  const [timezone, setTimezone] = useState<string>(pack.schedule_timezone || 'UTC');
  const [continuous, setContinuous] = useState<boolean>(Boolean(pack.continuous));
  const [webhook, setWebhook] = useState<string>('');
  const [webhookEdited, setWebhookEdited] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<string | null>(null);

  const choice = { kind, every };
  const intervalProblem = validateInterval(choice);
  const scheduled = kind !== 'none';
  const hasSavedWebhook = Boolean(pack.notify_webhook_url);

  async function save() {
    if (intervalProblem) {
      setError(intervalProblem);
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const body: Record<string, unknown> = {
        schedule: buildSchedule(choice),
        schedule_enabled: scheduled && enabled,
        schedule_timezone: timezone.trim() || 'UTC',
        continuous,
      };
      if (webhookEdited) body.notify_webhook_url = webhook.trim();
      await patch(`/validation-packs/${pack.id}`, body);
      setWebhook('');
      setWebhookEdited(false);
      setSavedAt(new Date().toLocaleTimeString());
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the schedule.');
    } finally {
      setSaving(false);
    }
  }

  const zones = knownTimezones();
  const live = !isNotScheduled(pack.schedule) && pack.schedule_enabled;

  return (
    <Card style={{ marginBottom: 20 }}>
      <div aria-label="Schedule settings" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 16, flexWrap: 'wrap' }}>
          <span style={LABEL}>Schedule</span>
          <span style={{ fontWeight: 600 }}>{describeSchedule(pack.schedule, pack.schedule_timezone)}</span>
          {live && pack.next_run_at && (
            <span style={{ fontSize: 12, color: P.textMute }}>
              Next run: {new Date(pack.next_run_at).toLocaleString()}
            </span>
          )}
          {pack.last_scheduled_run_at && (
            <span style={{ fontSize: 12, color: P.textMute }}>
              Last: {new Date(pack.last_scheduled_run_at).toLocaleString()}
            </span>
          )}
        </div>

        <div style={{ fontSize: 12, color: P.textMute }}>
          Scheduled runs happen in the background on the machine running Inspectra: no window opens, so you can keep
          working. They only run while Inspectra is running and the machine is awake.
        </div>

        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            <span style={LABEL}>Repeat</span>
            <select value={kind} onChange={e => setKind(e.target.value as ScheduleKind)} style={INPUT}>
              {(Object.keys(KIND_LABEL) as ScheduleKind[]).map(k => (
                <option key={k} value={k}>{KIND_LABEL[k]}</option>
              ))}
            </select>
          </label>

          {(kind === 'minutes' || kind === 'hours') && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={LABEL}>{kind === 'minutes' ? 'Minutes' : 'Hours'}</span>
              <input
                type="number"
                aria-label={kind === 'minutes' ? 'Minutes between runs' : 'Hours between runs'}
                value={Number.isFinite(every) ? every : ''}
                min={INTERVAL_LIMITS[kind].min}
                max={INTERVAL_LIMITS[kind].max}
                onChange={e => setEvery(e.target.value === '' ? NaN : Number(e.target.value))}
                style={{ ...INPUT, width: 90 }}
              />
            </label>
          )}

          {(kind === 'daily' || kind === 'weekdays') && (
            <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <span style={LABEL}>Timezone</span>
              <span style={{ display: 'flex', gap: 6 }}>
                <input
                  list="schedule-timezones"
                  aria-label="Timezone"
                  value={timezone}
                  onChange={e => setTimezone(e.target.value)}
                  style={{ ...INPUT, width: 200 }}
                />
                <Btn variant="ghost" onClick={() => setTimezone(browserTimezone())}>Use mine</Btn>
              </span>
              <datalist id="schedule-timezones">
                {zones.map(z => <option key={z} value={z} />)}
              </datalist>
            </label>
          )}
        </div>

        {scheduled && (
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13 }}>
            <input
              type="checkbox"
              checked={enabled}
              onChange={e => setEnabled(e.target.checked)}
              style={{ accentColor: P.accent }}
            />
            Run on this schedule
          </label>
        )}

        <label style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
          <input
            type="checkbox"
            checked={continuous}
            onChange={e => setContinuous(e.target.checked)}
            style={{ accentColor: P.accent, marginTop: 2 }}
          />
          <span>
            <span style={{ fontSize: 13 }}>Run each test case as one flow</span>
            <span style={{ display: 'block', fontSize: 11, color: P.textMute }}>
              Keeps the page and session between the steps of a test case, so typed text and logins carry over.
            </span>
          </span>
        </label>

        <label style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span style={LABEL}>Tell me when a scheduled run fails (webhook URL)</span>
          <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
            <input
              type="url"
              aria-label="Failure webhook URL"
              value={webhook}
              placeholder={hasSavedWebhook ? `Saved: ${pack.notify_webhook_url}` : 'https://… (optional)'}
              onChange={e => { setWebhook(e.target.value); setWebhookEdited(true); }}
              style={{ ...INPUT, flex: 1, minWidth: 220 }}
            />
            {hasSavedWebhook && !webhookEdited && (
              <Btn variant="ghost" onClick={() => { setWebhook(''); setWebhookEdited(true); }}>Remove</Btn>
            )}
          </span>
          <span style={{ fontSize: 11, color: P.textMute }}>
            Inspectra sends one JSON message with the pack, run and failed steps. Secrets are removed, and the saved
            address is never shown in full.
          </span>
        </label>

        {error && (
          <div role="alert" style={{ fontSize: 12, color: P.fail }}>{error}</div>
        )}

        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <Btn variant="primary" demoWrite onClick={save} disabled={saving || Boolean(intervalProblem)}>
            {saving ? 'Saving…' : 'Save schedule'}
          </Btn>
          {savedAt && !error && <span style={{ fontSize: 12, color: P.textMute }}>Saved at {savedAt}</span>}
        </div>
      </div>
    </Card>
  );
}
