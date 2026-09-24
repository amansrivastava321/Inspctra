import { AlertTriangle, CheckCircle2, CircleOff, ExternalLink, Images } from 'lucide-react';
import { P, F } from '../../design/tokens';
import type { DashboardFailedRun, Provenance } from '../../types/api';
import { Btn, Card } from '../layout/AppShell';
import { ProvenanceBadge } from '../ProvenanceBadge';
import { DashboardScreenshot } from './DashboardScreenshot';

export type DashboardState = 'failure' | 'clear' | 'empty' | 'offline';

export function relativeTime(value?: string | null, now = Date.now()): string {
  if (!value) return 'Time unavailable';
  const time = new Date(value).getTime();
  if (!Number.isFinite(time)) return 'Time unavailable';
  const seconds = Math.max(0, Math.round((now - time) / 1000));
  if (seconds < 60) return `${seconds} seconds ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.round(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
}

interface DashboardHeroProps {
  state: DashboardState;
  failure?: DashboardFailedRun | null;
  lastRunAt?: string | null;
  lastRunProvenance?: Provenance | null;
  passedRuns7d?: number;
  onNavigate: (path: string) => void;
  onRetry: () => void;
}

export function DashboardHero({
  state, failure, lastRunAt, lastRunProvenance, passedRuns7d = 0, onNavigate, onRetry,
}: DashboardHeroProps) {
  if (state === 'offline') {
    return (
      <Card style={{ minHeight: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', maxWidth: 500 }}>
          <CircleOff size={42} color={P.fail} aria-hidden="true" />
          <h1 style={{ margin: '14px 0 8px', fontSize: 28, color: P.text }}>Backend offline</h1>
          <p style={{ margin: '0 0 20px', color: P.textDim }}>Connect to your workspace to see test results.</p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
            <Btn variant="primary" onClick={onRetry}>Retry connection</Btn>
            <Btn onClick={() => onNavigate('/demo')}>Try Demo</Btn>
          </div>
        </div>
      </Card>
    );
  }

  if (state === 'empty') {
    return (
      <Card style={{ minHeight: 280, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center', maxWidth: 520 }}>
          <CircleOff size={42} color={P.textMute} aria-hidden="true" />
          <h1 style={{ margin: '14px 0 8px', fontSize: 28, color: P.text }}>No runs yet</h1>
          <p style={{ margin: '0 0 20px', color: P.textDim }}>
            Create your first validation pack to start testing
          </p>
          <div style={{ display: 'flex', justifyContent: 'center', gap: 8 }}>
            <Btn variant="primary" demoWrite onClick={() => onNavigate('/packs/new')}>Create Pack</Btn>
            <Btn onClick={() => onNavigate('/demo')}>Try Demo</Btn>
          </div>
        </div>
      </Card>
    );
  }

  if (state === 'clear') {
    return (
      <Card style={{ minHeight: 260, display: 'flex', alignItems: 'center', padding: 28 }}>
        <div style={{ display: 'flex', gap: 22, alignItems: 'center' }}>
          <div style={{
            width: 68, height: 68, borderRadius: 18, background: P.passSoft,
            color: P.pass, display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}><CheckCircle2 size={38} /></div>
          <div>
            <div style={{ fontSize: 11, color: P.textMute, fontFamily: F.mono, textTransform: 'uppercase' }}>
              What broke?
            </div>
            <h1 style={{ margin: '6px 0 10px', fontSize: 30, color: P.text }}>All systems clear</h1>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ color: P.textDim, fontSize: 13 }}>
                Last run passed {relativeTime(lastRunAt)}
              </span>
              <ProvenanceBadge provenance={lastRunProvenance} source="Dashboard last run" />
            </div>
            <p style={{ margin: '10px 0 0', color: P.pass, fontWeight: 600 }}>
              {passedRuns7d} runs passed in the last 7 days
            </p>
            {lastRunAt && (
              <div title={new Date(lastRunAt).toLocaleString()} style={{ marginTop: 5, color: P.textMute, fontSize: 11 }}>
                {new Date(lastRunAt).toLocaleString()}
              </div>
            )}
          </div>
        </div>
      </Card>
    );
  }

  if (!failure) return null;
  return (
    <Card style={{ padding: 24, borderColor: `${P.fail}55`, background: `linear-gradient(135deg, ${P.failSoft}, ${P.card} 54%)` }}>
      <div className="resp-detail-grid" style={{ gridTemplateColumns: 'minmax(0, 1.45fr) minmax(260px, 0.75fr)', gap: 24 }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <AlertTriangle size={18} color={P.fail} aria-hidden="true" />
            <h1 style={{ margin: 0, color: P.text, fontSize: 24 }}>What broke?</h1>
          </div>
          <div style={{ marginTop: 22, fontSize: 20, fontWeight: 650, color: P.text }}>
            {failure.app_name ?? 'App'} — {failure.pack_name ?? 'Validation pack'}
          </div>
          <p style={{ margin: '12px 0', fontSize: 14, color: P.textDim, lineHeight: 1.55 }}>
            {failure.failure_reason}
          </p>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ padding: '3px 9px', borderRadius: 999, background: P.failSoft, color: P.fail, fontSize: 11, fontWeight: 700 }}>
              Failed
            </span>
            <ProvenanceBadge provenance={failure.provenance} source="Dashboard failed run" />
            <span style={{ color: P.textMute, fontSize: 12 }}>
              Failed {relativeTime(failure.failed_at)}
            </span>
          </div>
          <div title={new Date(failure.failed_at).toLocaleString()} style={{ marginTop: 7, color: P.textMute, fontSize: 11 }}>
            {new Date(failure.failed_at).toLocaleString()}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 24 }}>
            <Btn variant="primary" onClick={() => onNavigate(`/runs/${failure.id}`)}>
              <ExternalLink size={13} />View Details
            </Btn>
            <Btn onClick={() => onNavigate(`/evidence?run_id=${encodeURIComponent(failure.id)}`)}>
              <Images size={13} />Investigate Evidence
            </Btn>
          </div>
        </div>
        <DashboardScreenshot
          evidenceId={failure.screenshot_evidence_id}
          provenance={failure.screenshot_provenance}
        />
      </div>
    </Card>
  );
}
