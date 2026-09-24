import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { get, post } from '../api/client';
import { DashboardActions } from '../components/dashboard/DashboardActions';
import { CoverageOverview } from '../components/dashboard/CoverageOverview';
import { DashboardHero } from '../components/dashboard/DashboardHero';
import type { DashboardState } from '../components/dashboard/DashboardHero';
import { FailureContext } from '../components/dashboard/FailureContext';
import { ErrorState, LoadingSkeleton } from '../components/common/EmptyState';
import { AppShell, Btn } from '../components/layout/AppShell';
import { useApi } from '../hooks/useApi';
import { useWorkspaceMode } from '../state/WorkspaceModeContext';
import type { DashboardSummary, LiveRunRecord } from '../types/api';

function getDashboard() {
  return get<DashboardSummary>('/dashboard');
}

export default function DashboardPage() {
  const nav = useNavigate();
  const { isDemo, toWorkspacePath } = useWorkspaceMode();
  const { data, loading, error, refetch, isOffline } = useApi(getDashboard, {
    demo: workspace => workspace.dashboard,
  });
  const [rerunning, setRerunning] = useState(false);
  const [rerunError, setRerunError] = useState('');
  const go = (path: string) => nav(toWorkspacePath(path));

  const state: DashboardState = isOffline
    ? 'offline'
    : !data || data.total_runs === 0 || (!data.recent_failed_run && !data.last_run_at)
      ? 'empty'
      : data.recent_failed_run
        ? 'failure'
        : 'clear';

  const rerun = async () => {
    const failed = data?.recent_failed_run;
    if (!failed || isDemo) return;
    setRerunning(true);
    setRerunError('');
    try {
      const run = await post<LiveRunRecord>(`/validation-packs/${encodeURIComponent(failed.pack_id)}/runs`, {
        app_target_id: failed.app_target_id,
        execution_mode: 'automated',
      });
      go(`/runs/${run.id}`);
    } catch (err) {
      setRerunError(err instanceof Error ? err.message : String(err));
    } finally {
      setRerunning(false);
    }
  };

  return (
    <AppShell
      section="workspace"
      title="Dashboard"
      provenance={data?.provenance}
      provenanceSource={data ? 'Dashboard summary' : undefined}
      actions={!isOffline ? (
        <Btn size="sm" variant="ghost" onClick={refetch} aria-label="Refresh dashboard">
          <RefreshCw size={13} />Refresh
        </Btn>
      ) : undefined}
    >
      {loading ? (
        <LoadingSkeleton rows={7} />
      ) : error && !isOffline && !data ? (
        <ErrorState message={error} onRetry={refetch} />
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <h1 className="page-header-title" style={{ fontSize: 22, fontWeight: 600, color: '#ececf1', margin: '0 0 4px' }}>
            Dashboard
          </h1>
          <DashboardHero
            state={state}
            failure={data?.recent_failed_run}
            lastRunAt={data?.last_run_at}
            lastRunProvenance={data?.last_run_provenance}
            passedRuns7d={data?.passed_runs_7d}
            onNavigate={go}
            onRetry={refetch}
          />

          {data && state === 'failure' && (
            <FailureContext
              reasons={data.failure_reasons ?? []}
              days={data.pass_rate_7d ?? []}
              provenance={data.provenance}
              onNavigate={go}
            />
          )}

          {data && state === 'clear' && data.coverage && (
            <CoverageOverview
              projects={data.projects_count ?? data.project_count}
              apps={data.apps_count ?? data.app_target_count}
              packs={data.packs_count ?? data.validation_pack_count}
              coverage={data.coverage}
              provenance={data.provenance}
            />
          )}

          {data && state !== 'offline' && (
            <DashboardActions
              state={state}
              failedRunId={data.recent_failed_run?.id}
              rerunning={rerunning}
              rerunError={rerunError}
              onNavigate={go}
              onRerun={rerun}
            />
          )}
        </div>
      )}
    </AppShell>
  );
}
