import { AppShell, PageHeader, Btn } from '../components/layout/AppShell';
import { ReportSummaryCard } from '../components/reports/ReportSummaryCard';
import { LoadingSkeleton, ErrorState, OfflineState, EmptyState, StaleDataState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { get } from '../api/client';
import type { ReportRecord } from '../types/api';
import { useWorkspaceNavigate } from '../state/WorkspaceModeContext';

function getReports() { return get<ReportRecord[]>('/reports'); }

export default function ReportsPage() {
  const nav = useWorkspaceNavigate();
  const { data, loading, error, refetch, isOffline, fetchedAt } = useApi(getReports, { demo: workspace => workspace.reports });

  return (
    <AppShell section="06" title="Reports">
      <PageHeader title="Reports" subtitle={`${data?.length ?? 0} reports generated`} />

      <StaleDataState fetchedAt={fetchedAt} onRefresh={refetch} />

      {loading ? <LoadingSkeleton /> : isOffline ? <OfflineState onRetry={refetch} /> : error && !data ? <ErrorState message={error} onRetry={refetch} /> :
        !data?.length ? (
          <EmptyState
            title="No reports generated yet"
            description="Reports are generated automatically after test runs complete."
            action={<Btn variant="primary" onClick={() => nav('/packs')}>Run a Pack</Btn>}
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {(data ?? []).map(rep => (
              <ReportSummaryCard key={rep.id} report={rep} onClick={() => nav(`/reports/${rep.id}`)} />
            ))}
          </div>
        )}
    </AppShell>
  );
}
