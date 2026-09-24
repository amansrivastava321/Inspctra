import { useCallback } from 'react';
import { AlertTriangle, History } from 'lucide-react';

import { getRunHistory } from '../../../api/client';
import { F, P } from '../../../design/tokens';
import { useApi } from '../../../hooks/useApi';
import { useWorkspaceMode, useWorkspaceNavigate } from '../../../state/WorkspaceModeContext';
import type { RunHistoryItem, RunHistoryResponse } from '../../../types/api';
import { ProvenanceBadge } from '../../ProvenanceBadge';
import { Card } from '../../layout/AppShell';
import { HistoricalRunCitation } from './HistoricalRunCitation';
import { RepeatedFailureList } from './RepeatedFailureList';
import { RunHistorySummary } from './RunHistorySummary';
import { StepHistoryTable } from './StepHistoryTable';


export interface RunHistoryPanelProps {
  runId: string;
  onSelectStep?: (stepId: string) => void;
}

function label(value: string): string {
  return value.replace(/_/g, ' ');
}

function HistoricalRunRow({
  item,
  onOpenRun,
}: {
  item: RunHistoryItem;
  onOpenRun: (runId: string) => void;
}) {
  return (
    <div style={{ padding: 9, borderRadius: 8, border: `1px solid ${P.border}`, background: P.cardHi }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 7 }}>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 7 }}>
          <span style={{ color: P.text, fontSize: 11 }}>{item.status}</span>
          <span style={{ color: P.textMute, fontSize: 10 }}>
            {item.execution_mode === 'manual' ? 'Manual' : 'Automated'}
          </span>
          {item.exclusion_reason && (
            <span style={{ color: P.textMute, fontSize: 10 }}>
              excluded: {label(item.exclusion_reason)}
            </span>
          )}
        </div>
        <ProvenanceBadge provenance={item.provenance} source={`historical run ${item.run_id}`} />
      </div>
      <div style={{ marginTop: 7 }}>
        <HistoricalRunCitation citation={item.citation} onOpenRun={onOpenRun} />
      </div>
    </div>
  );
}

function PanelState({ children, tone = 'neutral' }: { children: React.ReactNode; tone?: 'neutral' | 'error' }) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      style={{ color: tone === 'error' ? P.fail : P.textMute, fontSize: 11, lineHeight: 1.5 }}
    >
      {children}
    </div>
  );
}

export function RunHistoryPanel({ runId, onSelectStep }: RunHistoryPanelProps) {
  const nav = useWorkspaceNavigate();
  const { isDemo } = useWorkspaceMode();
  const loadHistory = useCallback(() => getRunHistory(runId), [runId]);
  const { data, loading, error } = useApi<RunHistoryResponse>(loadHistory, { skip: isDemo });
  const openRun = useCallback((historicalRunId: string) => {
    nav(`/runs/${encodeURIComponent(historicalRunId)}`);
  }, [nav]);

  const body = (() => {
    if (isDemo) return <PanelState>Historical context is unavailable in the demo workspace.</PanelState>;
    if (loading) return <PanelState>Loading historical context…</PanelState>;
    if (error || !data) return <PanelState tone="error">Run history could not be loaded.</PanelState>;

    const noHistory = data.recent_runs.length === 0 && data.manual_observations.length === 0;
    if (noHistory) return <PanelState>No comparable historical runs were found.</PanelState>;

    const onlyNonFactual = data.considered_runs === 0;
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 13 }}>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <span style={{ color: P.textDim, fontSize: 10 }}>{data.considered_runs} considered</span>
          <span style={{ color: P.textMute, fontSize: 10 }}>{data.excluded_runs} excluded</span>
          <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>
            exact pack + target scope
          </span>
        </div>

        {data.insufficient_history && (
          <div role="note" style={{ padding: '8px 10px', borderRadius: 7, border: `1px solid ${P.unclear}33`, background: P.unclearSoft, color: P.textDim, fontSize: 11 }}>
            Not enough comparable real-execution history is available to establish a reliable pattern. Exact observations remain visible below.
          </div>
        )}

        {data.comparability_warnings.map((warning, index) => (
          <div key={`${warning}-${index}`} role="note" style={{ display: 'flex', gap: 7, padding: '8px 10px', borderRadius: 7, border: `1px solid ${P.borderHi}`, background: P.surface, color: P.textDim, fontSize: 11 }}>
            <AlertTriangle size={13} color={P.unclear} aria-hidden style={{ flexShrink: 0, marginTop: 1 }} />
            {warning}
          </div>
        ))}

        {onlyNonFactual ? (
          <PanelState>No comparable automated real-execution history is available. Manual and excluded observations remain separate below.</PanelState>
        ) : (
          <RunHistorySummary history={data} onOpenRun={openRun} />
        )}

        {Object.keys(data.exclusions_by_reason).length > 0 && (
          <section aria-label="History exclusions">
            <h4 style={{ color: P.text, fontSize: 11, margin: '0 0 7px' }}>Excluded observations</h4>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {Object.entries(data.exclusions_by_reason).map(([reason, count]) => (
                <span key={reason} style={{ padding: '3px 7px', borderRadius: 999, border: `1px solid ${P.border}`, background: P.cardHi, color: P.textMute, fontSize: 10 }}>
                  {label(reason)} · {count}
                </span>
              ))}
            </div>
          </section>
        )}

        <StepHistoryTable
          steps={data.step_history}
          onOpenRun={openRun}
          onSelectStep={onSelectStep}
        />
        <RepeatedFailureList
          signatures={data.repeated_failure_signatures}
          onOpenRun={openRun}
          onSelectStep={onSelectStep}
        />

        {data.manual_observations.length > 0 && (
          <section role="region" aria-label="Manual observations">
            <h4 style={{ color: P.text, fontSize: 11, margin: '0 0 7px' }}>Manual observations</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {data.manual_observations.map(item => (
                <HistoricalRunRow key={item.run_id} item={item} onOpenRun={openRun} />
              ))}
            </div>
          </section>
        )}

        {data.recent_runs.length > 0 && (
          <section aria-label="Recent comparable runs">
            <h4 style={{ color: P.text, fontSize: 11, margin: '0 0 7px' }}>Recent comparable runs</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
              {data.recent_runs.map(item => (
                <HistoricalRunRow key={item.run_id} item={item} onOpenRun={openRun} />
              ))}
            </div>
          </section>
        )}
      </div>
    );
  })();

  return (
    <Card>
      <section aria-labelledby={`run-history-${runId}`} style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div>
          <h3 id={`run-history-${runId}`} style={{ display: 'flex', alignItems: 'center', gap: 6, margin: 0, color: P.text, fontSize: 11 }}>
            <History size={14} color={P.accent} aria-hidden />
            Historical Context
          </h3>
          <div style={{ color: P.textMute, fontSize: 10, marginTop: 4 }}>
            Deterministic records for this exact validation pack and app target.
          </div>
        </div>
        {body}
      </section>
    </Card>
  );
}
