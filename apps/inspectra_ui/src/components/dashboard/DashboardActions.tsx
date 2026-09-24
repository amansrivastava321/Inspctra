import { Cable, CalendarClock, FileSearch, Play, Plus, ShieldCheck } from 'lucide-react';
import { P } from '../../design/tokens';
import { PreviewBadge } from '../PreviewBadge';
import { Btn, Card } from '../layout/AppShell';
import type { DashboardState } from './DashboardHero';

interface DashboardActionsProps {
  state: Exclude<DashboardState, 'offline'>;
  failedRunId?: string;
  rerunning?: boolean;
  rerunError?: string;
  onNavigate: (path: string) => void;
  onRerun: () => void;
}

export function DashboardActions({
  state, failedRunId, rerunning = false, rerunError, onNavigate, onRerun,
}: DashboardActionsProps) {
  return (
    <section aria-labelledby="dashboard-next-heading">
      <h2 id="dashboard-next-heading" style={{ margin: '0 0 10px', fontSize: 18, color: P.text }}>What next?</h2>
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          {state === 'failure' && (
            <>
              <Btn variant="primary" demoWrite disabled={rerunning} onClick={onRerun}>
                <Play size={13} />{rerunning ? 'Starting run…' : 'Re-run failed pack'}
              </Btn>
              <Btn demoWrite onClick={() => onNavigate('/packs/new')}><Plus size={13} />Create new pack</Btn>
              <Btn onClick={() => onNavigate(failedRunId ? `/evidence?run_id=${encodeURIComponent(failedRunId)}` : '/evidence')}>
                <FileSearch size={13} />Review evidence
              </Btn>
            </>
          )}
          {state === 'clear' && (
            <>
              <Btn variant="primary" demoWrite onClick={() => onNavigate('/packs/new')}><Plus size={13} />Create new validation pack</Btn>
              <Btn onClick={() => onNavigate('/projects?view=apps&coverage=missing')}><ShieldCheck size={13} />Review coverage</Btn>
              <span title="Scheduling will be available in a future release." style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}>
                <Btn disabled><CalendarClock size={13} />Schedule next run</Btn>
                <PreviewBadge />
              </span>
            </>
          )}
          {state === 'empty' && (
            <>
              <Btn variant="primary" demoWrite onClick={() => onNavigate('/packs/new')}><Plus size={13} />Create your first pack</Btn>
              <Btn demoWrite onClick={() => onNavigate('/projects/new')}><Cable size={13} />Connect an app</Btn>
              <Btn onClick={() => onNavigate('/demo')}>Try Demo</Btn>
            </>
          )}
        </div>
        {rerunError && (
          <div role="alert" style={{ marginTop: 12, color: P.fail, fontSize: 12 }}>
            Could not start the pack: {rerunError}
          </div>
        )}
      </Card>
    </section>
  );
}
