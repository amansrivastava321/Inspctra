import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import {
  ArrowLeft,
  RefreshCw,
  FileText,
  RotateCcw,
  AlertTriangle,
  Check,
  X,
  Ban,
  FastForward,
  Upload,
  Shield,
  Download,
} from 'lucide-react';
import { P, F } from '../design/tokens';
import { AppShell, Card, Btn } from '../components/layout/AppShell';
import { StepTimeline } from '../components/live-run/StepTimeline';
import { LiveAppFrame } from '../components/live-run/LiveAppFrame';
import { VisualRegressionCard } from '../components/live-run/VisualRegressionCard';
import { VerdictPanel } from '../components/live-run/VerdictPanel';
import { EventStreamDrawer } from '../components/live-run/EventStreamDrawer';
import { RuntimeFlowMap } from '../components/runtime/RuntimeFlowMap';
import { ReportDownloadButtons } from '../components/reports/ReportDownloadButtons';
import { EvidenceCard } from '../components/evidence/EvidenceCard';
import { EvidencePanel } from '../components/evidence/EvidencePanel';
import { FailureDetails } from '../components/live-run/FailureDetails';
import { AIRootCauseSuggestions } from '../components/live-run/AIRootCauseSuggestions';
import { RunHistoryPanel } from '../components/live-run/history/RunHistoryPanel';
import { RunComparisonPanel } from '../components/live-run/comparison/RunComparisonPanel';
import { PermissionModal } from '../components/modals/PermissionModal';
import { LoadingSkeleton, ErrorState } from '../components/common/EmptyState';
import { useApi } from '../hooks/useApi';
import { useWorkspaceMode, useWorkspaceNavigate } from '../state/WorkspaceModeContext';
import { useRunStream } from '../hooks/useRunStream';
import { usePermissionRequests } from '../hooks/usePermissionRequests';
import {
  get,
  post,
  generateReport,
  retestFailed,
  evaluateRunEvidence,
  getRunEvaluation,
  evidenceDownloadUrl,
  baselineDownloadUrl,
} from '../api/client';
import {
  saveManualStepVerdict,
  uploadManualEvidence,
  finalizeManualRun,
} from '../api/validationPacks';
import type { LiveRunRecord, StepResult, EvidenceFile, AIEvaluationNote, DurableRunEvent } from '../types/api';

export function toDisplaySteps(run: LiveRunRecord | undefined): StepResult[] {
  if (!run) return [];
  const baseSteps = run.steps || [];
  const results = run.step_results || [];
  if (baseSteps.length === 0) {
    return results.map((result, idx) => ({
      ...result,
      index: result.index || result.step || idx + 1,
      id: result.id || result.step_id,
      step_id: result.step_id,
      name: result.name || `${result.action_type?.replace(/_/g, ' ') || 'step'} ${result.step || idx + 1}`,
      warning: (result as any).warning,
    }));
  }
  return baseSteps.map((step, idx) => {
    const result = results.find((item) => item.step_id === step.step_id || item.step === idx + 1);
    return {
      index: idx + 1,
      id: step.step_id,
      step_id: step.step_id,
      name: step.description || `${step.action_type.replace(/_/g, ' ')} ${idx + 1}`,
      status: result?.status || 'pending',
      error: result?.error,
      expected: result?.expected ?? step.expected,
      actual: result?.actual,
      actual_result: result?.actual_result,
      notes: result?.notes,
      failure_reason: result?.failure_reason,
      tester_name: result?.tester_name,
      action_type: result?.action_type || step.action_type,
      method: result?.method || step.method,
      url: result?.url || step.url,
      status_code: result?.status_code,
      response_time_ms: result?.response_time_ms,
      assertion_result: result?.assertion_result,
      evidence_ids: result?.evidence_ids || [],
      evidence_count: result?.evidence_count ?? result?.evidence_ids?.length,
      duration_ms: result?.duration_ms,
      started_at: result?.started_at,
      completed_at: result?.completed_at,
      optional: step.optional,
      budget_ms: step.budget_ms,
      warn_ms: step.warn_ms,
      metric_name: step.metric_name,
      warning: (result as any)?.warning,
      provenance: result?.provenance,
    };
  });
}

function runDurationMs(run: LiveRunRecord): number | undefined {
  if (run.elapsed_ms != null) return run.elapsed_ms;
  const started = run.started_at || run.created_at;
  const completed = run.completed_at || run.finished_at;
  if (!started || !completed) return undefined;
  const duration = Date.parse(completed) - Date.parse(started);
  return Number.isFinite(duration) && duration >= 0 ? duration : undefined;
}

interface A11yViolation {
  rule_id: string;
  description: string;
  impact: string;
  selector: string;
  html: string;
}

interface A11yPass {
  rule_id: string;
  description: string;
}

interface A11yResult {
  total_violations: number;
  violations: A11yViolation[];
  passes: A11yPass[];
}

function AccessibilityViolationsCard({ a11yResult }: { a11yResult: A11yResult }) {
  const violations = a11yResult.violations || [];
  const passes = a11yResult.passes || [];

  return (
    <Card>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          ACCESSIBILITY AUDIT SUMMARY
        </div>
        
        <div style={{ display: 'flex', gap: 15 }}>
          <div style={{ padding: '8px 16px', background: `${P.fail}10`, border: `1px solid ${P.fail}25`, borderRadius: 6, display: 'flex', flexDirection: 'column', minWidth: 120 }}>
            <span style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>VIOLATIONS</span>
            <span style={{ fontSize: 22, fontWeight: 700, color: violations.length > 0 ? P.fail : P.pass, marginTop: 2 }}>
              {violations.length}
            </span>
          </div>
          <div style={{ padding: '8px 16px', background: `${P.pass}10`, border: `1px solid ${P.pass}25`, borderRadius: 6, display: 'flex', flexDirection: 'column', minWidth: 120 }}>
            <span style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>PASSED RULES</span>
            <span style={{ fontSize: 22, fontWeight: 700, color: P.pass, marginTop: 2 }}>
              {passes.length}
            </span>
          </div>
        </div>

        {violations.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 4 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: P.textDim }}>VIOLATION DETAILS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 300, overflowY: 'auto', paddingRight: 4 }}>
              {violations.map((v, i) => {
                const badgeColor = v.impact === 'critical' ? P.fail : v.impact === 'serious' ? P.unclear : P.textMute;
                return (
                  <div key={i} style={{ padding: 10, background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: P.text }}>{v.rule_id}</span>
                      <span style={{ fontSize: 9, fontFamily: F.mono, fontWeight: 600, color: badgeColor, background: `${badgeColor}15`, border: `1px solid ${badgeColor}30`, padding: '1px 4px', borderRadius: 4, textTransform: 'uppercase' }}>
                        {v.impact}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim }}>{v.description}</div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>SELECTOR:</div>
                      <code style={{ fontSize: 10, fontFamily: F.mono, background: P.card, padding: '2px 4px', borderRadius: 4, overflowX: 'auto', whiteSpace: 'nowrap' }}>
                        {v.selector}
                      </code>
                    </div>
                    {v.html && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>ELEMENT HTML:</div>
                        <code style={{ fontSize: 10, fontFamily: F.mono, background: P.card, padding: '4px 6px', borderRadius: 4, overflowX: 'auto', whiteSpace: 'nowrap', color: P.accent }}>
                          {v.html}
                        </code>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 11, color: P.pass, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>✓</span> No accessibility violations detected.
          </div>
        )}
      </div>
    </Card>
  );
}

interface SecurityFinding {
  id: string;
  title: string;
  severity: string;
  description: string;
  recommendation?: string;
  category?: string;
  url?: string;
  header?: string;
  cookie?: string;
  affected_url?: string;
  affected_header?: string;
  affected_cookie?: string;
}

export function SecurityFindingsCard({ findings }: { findings: SecurityFinding[] }) {
  return (
    <Card>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            PASSIVE SECURITY SWEEP SUMMARY
          </div>
          <span style={{
            fontSize: 9, fontWeight: 700, fontFamily: F.mono,
            color: P.pass, background: `${P.pass}12`, border: `1px solid ${P.pass}33`,
            borderRadius: 4, padding: '2px 6px'
          }}>
            Passive check. No attack traffic sent.
          </span>
        </div>

        <div style={{ display: 'flex', gap: 15 }}>
          <div style={{ padding: '8px 16px', background: `${P.fail}10`, border: `1px solid ${P.fail}25`, borderRadius: 6, display: 'flex', flexDirection: 'column', minWidth: 120 }}>
            <span style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>TOTAL FINDINGS</span>
            <span style={{ fontSize: 22, fontWeight: 700, color: findings.length > 0 ? P.fail : P.pass, marginTop: 2 }}>
              {findings.length}
            </span>
          </div>
          <div style={{ padding: '8px 16px', background: `${P.unclear}10`, border: `1px solid ${P.unclear}25`, borderRadius: 6, display: 'flex', flexDirection: 'column', minWidth: 120 }}>
            <span style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>CRITICAL / HIGH</span>
            <span style={{ fontSize: 22, fontWeight: 700, color: findings.some(f => ['critical', 'high'].includes(f.severity)) ? P.fail : P.textMute, marginTop: 2 }}>
              {findings.filter(f => ['critical', 'high'].includes(f.severity)).length}
            </span>
          </div>
        </div>

        {findings.length > 0 ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 4 }}>
            <div style={{ fontSize: 10, fontWeight: 600, color: P.textDim }}>FINDINGS DETAILS</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 300, overflowY: 'auto', paddingRight: 4 }}>
              {findings.map((f, i) => {
                const badgeColor = ['critical', 'high'].includes(f.severity) ? P.fail : f.severity === 'medium' ? P.unclear : P.textMute;
                return (
                  <div key={i} style={{ padding: 10, background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6, display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <span style={{ fontSize: 11, fontWeight: 600, color: P.text }}>{f.title}</span>
                      <span style={{ fontSize: 9, fontFamily: F.mono, fontWeight: 600, color: badgeColor, background: `${badgeColor}15`, border: `1px solid ${badgeColor}30`, padding: '1px 4px', borderRadius: 4, textTransform: 'uppercase' }}>
                        {f.severity}
                      </span>
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim }}>{f.description}</div>
                    {f.recommendation && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>RECOMMENDATION:</div>
                        <div style={{ fontSize: 11, color: P.pass }}>{f.recommendation}</div>
                      </div>
                    )}
                    {f.category && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                        <span style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>CATEGORY:</span>
                        <code style={{ fontSize: 10, fontFamily: F.mono, background: P.card, padding: '1px 4px', borderRadius: 4 }}>
                          {f.category}
                        </code>
                      </div>
                    )}
                    {(f.url || f.affected_url) && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>AFFECTED URL:</div>
                        <code style={{ fontSize: 10, fontFamily: F.mono, background: P.card, padding: '2px 4px', borderRadius: 4, overflowX: 'auto', whiteSpace: 'nowrap' }}>
                          {f.url || f.affected_url}
                        </code>
                      </div>
                    )}
                    {(f.header || f.affected_header) && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>AFFECTED HEADER:</div>
                        <code style={{ fontSize: 10, fontFamily: F.mono, background: P.card, padding: '2px 4px', borderRadius: 4, overflowX: 'auto', whiteSpace: 'nowrap' }}>
                          {f.header || f.affected_header}
                        </code>
                      </div>
                    )}
                    {(f.cookie || f.affected_cookie) && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>AFFECTED COOKIE:</div>
                        <code style={{ fontSize: 10, fontFamily: F.mono, background: P.card, padding: '2px 4px', borderRadius: 4, overflowX: 'auto', whiteSpace: 'nowrap' }}>
                          {f.cookie || f.affected_cookie}
                        </code>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <div style={{ fontSize: 11, color: P.pass, display: 'flex', alignItems: 'center', gap: 6 }}>
            <span>✓</span> No passive security findings detected.
          </div>
        )}
      </div>
    </Card>
  );
}

function PerformanceMetricsCard({ metrics }: { metrics: Record<string, number> }) {
  return (
    <Card>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          PAGE PERFORMANCE TIMING METRICS
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 10 }}>
          <div style={{ padding: '8px 12px', background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6 }}>
            <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>TOTAL LOAD TIME</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.accent, marginTop: 2 }}>{metrics.total_load_ms != null ? `${metrics.total_load_ms}ms` : '—'}</div>
          </div>
          <div style={{ padding: '8px 12px', background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6 }}>
            <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>FIRST BYTE</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text, marginTop: 2 }}>{metrics.first_byte_ms != null ? `${metrics.first_byte_ms}ms` : '—'}</div>
          </div>
          <div style={{ padding: '8px 12px', background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6 }}>
            <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>DOM CONTENT LOADED</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text, marginTop: 2 }}>{metrics.dom_content_loaded_ms != null ? `${metrics.dom_content_loaded_ms}ms` : '—'}</div>
          </div>
          <div style={{ padding: '8px 12px', background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6 }}>
            <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>LOAD EVENT</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text, marginTop: 2 }}>{metrics.load_event_ms != null ? `${metrics.load_event_ms}ms` : '—'}</div>
          </div>
          <div style={{ padding: '8px 12px', background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6 }}>
            <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>RESOURCE COUNT</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text, marginTop: 2 }}>{metrics.resource_count != null ? metrics.resource_count : '—'}</div>
          </div>
          <div style={{ padding: '8px 12px', background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 6 }}>
            <div style={{ fontSize: 9, color: P.textMute, fontFamily: F.mono }}>TRANSFER SIZE</div>
            <div style={{ fontSize: 14, fontWeight: 600, color: P.text, marginTop: 2 }}>{metrics.total_transfer_size != null ? `${(metrics.total_transfer_size / 1024).toFixed(1)} KB` : '—'}</div>
          </div>
        </div>
      </div>
    </Card>
  );
}

function getEvidenceType(ev: EvidenceFile) {
  return ev.evidence_type ?? ev.type;
}

function formatMetadata(value: unknown) {
  if (value == null) return '—';
  if (typeof value === 'string') return value;
  return JSON.stringify(value, null, 2);
}

function normalizeEvaluationNotes(value: AIEvaluationNote[] | { notes: AIEvaluationNote[] } | null | undefined): AIEvaluationNote[] {
  if (!value) return [];
  return Array.isArray(value) ? value : value.notes || [];
}

function renderStringList(items: string[] | undefined) {
  if (!items || items.length === 0) return '—';
  return items.join(', ');
}

export default function LiveRunDetailWorkspace() {
  const { runId } = useParams<{ runId: string }>();
  const nav = useWorkspaceNavigate();
  const { isDemo } = useWorkspaceMode();
  const [selectedStep, setSelectedStep] = useState<StepResult | null>(null);
  const [generatingReport, setGeneratingReport] = useState(false);
  const [reportError, setReportError] = useState('');
  const [retesting, setRetesting] = useState(false);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [aiNotes, setAiNotes] = useState<AIEvaluationNote[]>([]);
  const [aiLoading, setAiLoading] = useState(false);
  const [aiError, setAiError] = useState('');

  // Manual execution states
  const [testerName, setTesterName] = useState(() => {
    try { return window.localStorage?.getItem('inspectra_tester_name') || ''; }
    catch { return ''; }
  });
  const [actualResult, setActualResult] = useState('');
  const [notes, setNotes] = useState('');
  const [failureReason, setFailureReason] = useState('');
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [finishing, setFinishing] = useState(false);
  const [hasAutoSelected, setHasAutoSelected] = useState(false);

  const getRun = useCallback(() => get<LiveRunRecord>(`/runs/${runId}`), [runId]);
  const getEvidence = useCallback(() => get<EvidenceFile[]>(`/evidence?run_id=${runId}`), [runId]);
  const getDurableEvents = useCallback(() => get<DurableRunEvent[]>(`/runs/${runId}/events`), [runId]);

  const { data: run, loading: runLoading, error: runError, refetch } = useApi(getRun, {
    demo: workspace => workspace.liveRuns.find(r => r.id === runId) as LiveRunRecord,
  });
  const { data: evidence, error: evidenceError, refetch: refetchEvidence } = useApi(getEvidence, { demo: workspace => workspace.evidence.filter(item => item.run_id === runId) });
  const { data: durableEventData, refetch: refetchDurableEvents } = useApi(getDurableEvents, { demo: () => [] });
  const durableEvents = Array.isArray(durableEventData) ? durableEventData : [];

  // Visual baseline states
  const [baselines, setBaselines] = useState<any[]>([]);
  const [approvingStepId, setApprovingStepId] = useState<string | null>(null);
  const [approvedSteps, setApprovedSteps] = useState<Record<string, boolean>>({});

  const appId = run?.app_id || run?.app_target_id;

  const fetchBaselines = useCallback(async () => {
    if (isDemo || !appId) return;
    try {
      const data = await get<any[]>(`/baselines?app_id=${appId}`);
      setBaselines(data);
    } catch (err) {
      console.error('Failed to fetch baselines', err);
    }
  }, [appId, isDemo]);

  useEffect(() => {
    if (appId) {
      fetchBaselines();
    }
  }, [appId, fetchBaselines]);

  const handleApproveBaseline = async (stepId: string, evidenceId: string, baselineName: string) => {
    if (!appId) return;
    setApprovingStepId(stepId);
    try {
      await post('/baselines', {
        app_id: appId,
        step_id: stepId,
        baseline_name: baselineName,
        evidence_id: evidenceId,
      });
      setApprovedSteps(prev => ({ ...prev, [stepId]: true }));
      await fetchBaselines();
    } catch (err) {
      console.error('Failed to approve baseline', err);
      alert('Failed to approve baseline: ' + (err as Error).message);
    } finally {
      setApprovingStepId(null);
    }
  };

  const baseline = (selectedStep && baselines) ? baselines.find((b: any) => b.step_id === selectedStep.id) : null;
  const baselineUrl = baseline ? baselineDownloadUrl(baseline.id) : undefined;

  const isManual = run?.execution_mode === 'manual';
  const isRunning = run?.status === 'running' || (isManual && run?.status === 'pending');

  const streamActive = !isManual && (run?.status === 'pending' || run?.status === 'running');
  const { events, connected, error: streamError, terminal: streamTerminal } = useRunStream(runId ?? null, streamActive);
  const { pending: permPending, approve, deny } = usePermissionRequests(runId, isRunning && !isManual ? 2000 : 0);

  useEffect(() => {
    if (!streamTerminal) return;
    void Promise.all([refetch(), refetchEvidence(), refetchDurableEvents()]);
  }, [streamTerminal, refetch, refetchEvidence, refetchDurableEvents]);

  // Unified steps for manual run
  const displayedSteps = run && isManual
    ? (run.steps || []).map((step: any, idx: number) => {
        const result = (run.step_results || []).find((r: any) => r.step_id === step.step_id || r.step === idx + 1);
        return {
          id: step.step_id,
          step_id: step.step_id,
          index: idx + 1,
          name: step.description || `Step ${idx + 1}`,
          status: result?.status || 'pending',
          expected: result?.expected ?? step.expected,
          actual: result?.actual,
          actual_result: result?.actual_result,
          notes: result?.notes,
          failure_reason: result?.failure_reason,
          tester_name: result?.tester_name,
          evidence_ids: result?.evidence_ids || [],
          evidence_count: result?.evidence_count ?? result?.evidence_ids?.length,
          duration_ms: result?.duration_ms,
          started_at: result?.started_at,
          completed_at: result?.completed_at,
          optional: step.optional,
          budget_ms: step.budget_ms,
          warn_ms: step.warn_ms,
          metric_name: step.metric_name,
          warning: result?.warning,
          provenance: result?.provenance,
        } as StepResult;
      })
    : toDisplaySteps(run ?? undefined);

  // Auto-select first uncompleted step on manual load
  useEffect(() => {
    if (run && isManual && !selectedStep && !hasAutoSelected && displayedSteps.length > 0) {
      const firstPending = displayedSteps.find(s => s.status === 'pending') || displayedSteps[0];
      if (firstPending) {
        setSelectedStep(firstPending);
        setHasAutoSelected(true);
      }
    }
  }, [run, isManual, selectedStep, hasAutoSelected, displayedSteps]);

  useEffect(() => {
    if (run && !isManual && !selectedStep && displayedSteps.length > 0) {
      setSelectedStep(
        displayedSteps.find((step) => step.status === 'failed' || step.status === 'error')
        || displayedSteps[0],
      );
    }
  }, [run, isManual, selectedStep, displayedSteps]);

  // Sync form inputs when selectedStep changes
  useEffect(() => {
    if (selectedStep && run && isManual) {
      const res = (run.step_results || []).find((r: any) => r.step_id === selectedStep.step_id || r.step === selectedStep.index);
      setActualResult(res?.actual_result || '');
      setNotes(res?.notes || '');
      setFailureReason(res?.failure_reason || '');
    }
  }, [selectedStep, run, isManual]);

  const handleSaveResult = async (status: string) => {
    if (!runId || !selectedStep?.id) return;
    try {
      localStorage.setItem('inspectra_tester_name', testerName);
      const updatedRun = await saveManualStepVerdict(runId, selectedStep.id, {
        status,
        actual_result: actualResult,
        notes,
        failure_reason: status === 'failed' || status === 'blocked' ? failureReason : undefined,
        tester_name: testerName,
      });
      await Promise.all([refetch(), refetchEvidence(), refetchDurableEvents()]);
      const updatedSteps = toDisplaySteps(updatedRun);
      // Auto-advance to next step
      const currentIdx = updatedSteps.findIndex(s => s.step_id === selectedStep.step_id);
      if (currentIdx !== -1 && currentIdx < updatedSteps.length - 1) {
        setSelectedStep(updatedSteps[currentIdx + 1]);
      } else if (currentIdx !== -1) {
        setSelectedStep(updatedSteps[currentIdx]);
      }
    } catch (err) {
      alert(String(err));
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !runId || !selectedStep?.id) return;
    setUploading(true);
    setUploadError('');
    try {
      const name = file.name;
      let evidenceType = 'log';
      if (file.type.startsWith('image/')) {
        evidenceType = 'screenshot';
      }
      await uploadManualEvidence(runId, selectedStep.id, file, name, evidenceType);
      await Promise.all([refetch(), refetchEvidence(), refetchDurableEvents()]);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : String(err));
    } finally {
      setUploading(false);
    }
  };

  const handleFinalize = async () => {
    if (!runId) return;
    setFinishing(true);
    try {
      await finalizeManualRun(runId);
      await Promise.all([refetch(), refetchEvidence(), refetchDurableEvents()]);
      setSelectedStep(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : String(err));
    } finally {
      setFinishing(false);
    }
  };

  // Derive active runtime node from latest event
  const lastEvent = events[events.length - 1];
  const activeNode = lastEvent?.type === 'screenshot' ? 'app'
    : lastEvent?.type === 'api_call' ? 'backend'
    : lastEvent?.type === 'db_delta' ? 'db'
    : lastEvent?.type === 'ai_oracle' ? 'ai'
    : lastEvent?.type === 'step_start' ? 'driver'
    : lastEvent?.type === 'verdict' ? 'verdict'
    : undefined;

  // Evidence for selected step
  const stepEvidence = evidence?.filter(ev => ev.step_id === selectedStep?.id) ?? [];

  const webTimingEv = stepEvidence.find(ev => getEvidenceType(ev) === 'web_timing');
  const metrics = webTimingEv?.metadata_json?.metrics as Record<string, number> | undefined;

  const a11yEv = stepEvidence.find(ev => getEvidenceType(ev) === 'accessibility_violations');
  const a11yResult = a11yEv?.metadata_json?.a11y_result as A11yResult | undefined;

  const secEv = stepEvidence.find(ev => getEvidenceType(ev) === 'security_findings');
  const secResult = secEv?.metadata_json as { findings?: any[] } | undefined;
  const securityFindings = secResult?.findings || (selectedStep as any)?.security_findings || [];

  const activeScreenshotEv = selectedStep
    ? stepEvidence.find(ev => getEvidenceType(ev) === 'screenshot')
    : evidence?.find(ev => getEvidenceType(ev) === 'screenshot');
  const screenshotUrl = activeScreenshotEv ? evidenceDownloadUrl(activeScreenshotEv.id) : undefined;

  const isFinished = run?.status != null && ['completed', 'failed', 'cancelled'].includes(run.status);
  const canEvaluateAi = run?.status == null || ['completed', 'failed', 'cancelled', 'blocked'].includes(run.status);
  const isReadOnly = isDemo || (run ? (run.status !== 'pending' && run.status !== 'running') : true);
  const hasRootCauseFailureSignal = Boolean(
    run?.error
    || run?.status === 'failed'
    || displayedSteps.some(step => ['failed', 'error', 'blocked', 'inconclusive', 'capability_gap'].includes(step.status)),
  );

  const loadAiNotes = useCallback(async () => {
    if (isDemo || !runId) return;
    try {
      const notes = await getRunEvaluation(runId);
      setAiNotes(normalizeEvaluationNotes(notes));
    } catch (err) {
      setAiError(err instanceof Error ? err.message : String(err));
    }
  }, [isDemo, runId]);

  useEffect(() => {
    void loadAiNotes();
  }, [loadAiNotes]);

  const handleGenerateReport = async () => {
    if (isDemo || !runId) return;
    setGeneratingReport(true);
    setReportError('');
    try {
      const report = await generateReport(runId);
      nav(`/reports/${report.id}`);
    } catch (err) {
      setReportError(err instanceof Error ? err.message : String(err));
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleRetest = async () => {
    if (isDemo || !runId) return;
    setRetesting(true);
    try {
      const newRun = await retestFailed(runId);
      nav(`/runs/${newRun.id}`);
    } catch (err) {
      setReportError(err instanceof Error ? err.message : String(err));
    } finally {
      setRetesting(false);
    }
  };

  const handleEvaluateAi = async () => {
    if (isDemo || !runId) return;
    setAiLoading(true);
    setAiError('');
    try {
      await evaluateRunEvidence(runId);
      await loadAiNotes();
    } catch (err) {
      setAiError(err instanceof Error ? err.message : String(err));
    } finally {
      setAiLoading(false);
    }
  };

  if (runLoading) return (
    <AppShell title="Loading run…"><LoadingSkeleton /></AppShell>
  );
  if (runError && !run) return (
    <AppShell title="Error"><ErrorState message={runError} onRetry={refetch} /></AppShell>
  );
  if (!run) return <AppShell title="Run not found"><ErrorState message="This run does not exist in this workspace." /></AppShell>;

  // Calculate if we can finalize
  const unreviewedRequiredSteps = displayedSteps.filter(s => !s.optional && s.status === 'pending');
  const canFinalize = unreviewedRequiredSteps.length === 0;
  const durationMs = runDurationMs(run);

  return (
    <AppShell
      section={isRunning ? '● LIVE' : run.status.toUpperCase()}
      title={run.pack_name ?? run.id.slice(0, 12)}
      provenance={run.provenance}
      provenanceSource="Live run detail"
      contentStyle={{ padding: 0, display: 'flex', flexDirection: 'column' }}
      actions={
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <Btn size="sm" variant="ghost" onClick={() => nav('/runs')}><ArrowLeft size={12} />Runs</Btn>
          <Btn size="sm" variant="ghost" onClick={refetch}><RefreshCw size={12} /></Btn>
          {durationMs != null && (
            <div style={{ display: 'flex', alignItems: 'baseline', gap: 6, padding: '4px 8px', borderRadius: 7, border: `1px solid ${P.border}`, background: P.surface }}>
              <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 9 }}>RUN DURATION</span>
              <span style={{ color: P.text, fontFamily: F.mono, fontSize: 11 }}>{(durationMs / 1000).toFixed(1)}s</span>
            </div>
          )}
          <a
            href={isDemo ? undefined : `/api/runs/${encodeURIComponent(run.id)}/evidence.zip`}
            aria-disabled={isDemo}
            title={isDemo ? 'Available in your real workspace. Leave demo to get started.' : 'Download screenshots, logs, HTML, and API evidence'}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 10px', borderRadius: 7, border: `1px solid ${P.border}`, background: P.cardHi, color: P.text, fontSize: 12, fontWeight: 500, textDecoration: 'none', pointerEvents: isDemo ? 'none' : 'auto', opacity: isDemo ? 0.5 : 1 }}
          >
            <Download size={12} />Download All Evidence
          </a>
          {isFinished && (
            <ReportDownloadButtons runId={run.id} compact />
          )}
          {isFinished && (
            <Btn
              size="sm" variant="secondary"
              onClick={handleRetest}
              disabled={isDemo || retesting}
              title={isDemo ? 'Available in your real workspace. Leave demo to get started.' : undefined}
              data-testid="retest-btn"
            >
              <RotateCcw size={12} />{retesting ? 'Retesting…' : 'Retest failed'}
            </Btn>
          )}
          {isFinished && (
            <Btn
              size="sm" variant="primary"
              onClick={handleGenerateReport}
              disabled={isDemo || generatingReport}
              title={isDemo ? 'Available in your real workspace. Leave demo to get started.' : undefined}
              data-testid="generate-report-btn"
            >
              <FileText size={12} />{generatingReport ? 'Generating…' : 'Generate report'}
            </Btn>
          )}
          {canEvaluateAi && (
            <Btn
              size="sm"
              variant="secondary"
              onClick={handleEvaluateAi}
              disabled={isDemo || aiLoading}
              title={isDemo ? 'Available in your real workspace. Leave demo to get started.' : undefined}
            >
              <Shield size={12} />{aiLoading ? 'Evaluating…' : 'Evaluate evidence with AI'}
            </Btn>
          )}
        </div>
      }
    >
      {reportError && (
        <div style={{ padding: '0 20px 8px' }}>
          <div style={{ padding: '8px 12px', borderRadius: 7, background: `${P.fail}22`,
            border: `1px solid ${P.fail}44`, fontSize: 12, color: P.fail }}>
            {reportError}
          </div>
        </div>
      )}

      {/* Permission modals */}
      {permPending.length > 0 && (
        <PermissionModal
          permission={permPending[0]}
          onApprove={approve}
          onDeny={deny}
          onClose={() => {}}
        />
      )}

      {/* Runtime flow map */}
      <div style={{ padding: '8px 20px', borderBottom: `1px solid ${P.border}`, background: P.surface }}>
        <RuntimeFlowMap activeNode={activeNode} compact />
      </div>

      {/* Evidence-first 60/40 investigation layout */}
      <div className="run-investigation-layout" style={{ flex: 1, overflow: 'hidden', minHeight: 0 }}>
        <div className="run-investigation-main">
        {/* Left: Step timeline */}
        <div className="run-timeline-column" style={{ width: 280, flexShrink: 0, borderRight: `1px solid ${P.border}`,
          overflowY: 'auto', background: P.surface }}>
          <div style={{ padding: '12px 14px', borderBottom: `1px solid ${P.border}` }}>
            <div style={{ fontSize: 10, color: P.textMute, fontFamily: "'JetBrains Mono',monospace",
              textTransform: 'uppercase', letterSpacing: '0.06em' }}>
              STEPS · {displayedSteps.length}
            </div>
          </div>
          <StepTimeline
            steps={displayedSteps}
            activeStepId={selectedStep?.id}
            onSelectStep={setSelectedStep}
          />
        </div>

        {/* Center column */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', minWidth: 0 }}>
          {isManual ? (
            /* Manual Testing Workspace */
            <div style={{ flex: 1, padding: 20, display: 'flex', flexDirection: 'column', gap: 16, overflowY: 'auto' }}>
              {selectedStep ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                  {/* Step Title & Type */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                    <div>
                      <h2 style={{ fontSize: 16, fontWeight: 600, color: P.text, margin: 0 }}>
                        Step {selectedStep.index}: {selectedStep.name}
                      </h2>
                      <div style={{ display: 'flex', gap: 6, marginTop: 6, alignItems: 'center' }}>
                        <span style={{
                          fontSize: 9, fontWeight: 700, letterSpacing: '0.04em', fontFamily: F.mono,
                          background: `${P.accent}18`, border: `1px solid ${P.accent}33`, borderRadius: 4,
                          padding: '1px 4px', color: P.accent, textTransform: 'uppercase'
                        }}>
                          {(run.steps?.[selectedStep.index - 1] as any)?.action_type || 'interaction'}
                        </span>
                        <span style={{
                          fontSize: 9, fontWeight: 700, letterSpacing: '0.04em', fontFamily: F.mono,
                          background: selectedStep.optional ? `${P.unclear}18` : `${P.accent}18`,
                          border: `1px solid ${selectedStep.optional ? P.unclear : P.accent}33`, borderRadius: 4,
                          padding: '1px 4px', color: selectedStep.optional ? P.unclear : P.accent,
                        }}>
                          {selectedStep.optional ? 'OPTIONAL' : 'REQUIRED'}
                        </span>
                      </div>
                    </div>
                    {isReadOnly && (
                      <span style={{
                        fontSize: 10, fontWeight: 700, background: `${P.pass}18`,
                        border: `1px solid ${P.pass}33`, color: P.pass, borderRadius: 4, padding: '2px 6px'
                      }}>
                        RUN FINALIZED
                      </span>
                    )}
                  </div>

                  {/* Step parameters */}
                  <div style={{
                    background: P.cardHi, border: `1px solid ${P.border}`, borderRadius: 8,
                    padding: 12, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12,
                  }}>
                    {((run.steps?.[selectedStep.index - 1] as any)?.target) && (
                      <div>
                        <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 10 }}>
                          {(run.steps?.[selectedStep.index - 1] as any)?.action_type === 'assert_visual_match' ? 'CSS Selector:' : 'Target / Selector:'}
                        </span>{' '}
                        <code style={{ fontFamily: F.mono, color: P.text }}>{((run.steps?.[selectedStep.index - 1] as any)?.target)}</code>
                      </div>
                    )}
                    {((run.steps?.[selectedStep.index - 1] as any)?.value) && (
                      <div>
                        <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 10 }}>
                          {(run.steps?.[selectedStep.index - 1] as any)?.action_type === 'assert_visual_match' ? 'Baseline Key:' : 'Value:'}
                        </span>{' '}
                        <code style={{ fontFamily: F.mono, color: P.text }}>{((run.steps?.[selectedStep.index - 1] as any)?.value)}</code>
                      </div>
                    )}
                    {((run.steps?.[selectedStep.index - 1] as any)?.expected) && (
                      <div>
                        <span style={{ color: P.textMute, fontFamily: F.mono, fontSize: 10 }}>
                          {(run.steps?.[selectedStep.index - 1] as any)?.action_type === 'assert_visual_match' ? 'Max Difference Threshold:' : 'Expected:'}
                        </span>{' '}
                        <code style={{ fontFamily: F.mono, color: P.text }}>{((run.steps?.[selectedStep.index - 1] as any)?.expected)}</code>
                      </div>
                    )}
                    {((run.steps?.[selectedStep.index - 1] as any)?.notes) && (
                      <div style={{ color: P.textMute, fontStyle: 'italic', marginTop: 4 }}>
                        {((run.steps?.[selectedStep.index - 1] as any)?.notes)}
                      </div>
                    )}
                  </div>

                  {/* Input Form */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>TESTER NAME</label>
                      <input
                        type="text"
                        placeholder="Enter your name"
                        disabled={isReadOnly}
                        value={testerName}
                        onChange={e => setTesterName(e.target.value)}
                        style={{
                          background: P.card, border: `1px solid ${P.border}`, borderRadius: 6,
                          padding: '8px 12px', color: P.text, fontSize: 12, outline: 'none',
                        }}
                      />
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>ACTUAL RESULT</label>
                        <textarea
                          placeholder="What did you observe?"
                          disabled={isReadOnly}
                          value={actualResult}
                          onChange={e => setActualResult(e.target.value)}
                          rows={3}
                          style={{
                            background: P.card, border: `1px solid ${P.border}`, borderRadius: 6,
                            padding: '8px 12px', color: P.text, fontSize: 12, outline: 'none',
                            resize: 'none', fontFamily: F.ui,
                          }}
                        />
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                        <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>NOTES / COMMENTS</label>
                        <textarea
                          placeholder="Any extra context?"
                          disabled={isReadOnly}
                          value={notes}
                          onChange={e => setNotes(e.target.value)}
                          rows={3}
                          style={{
                            background: P.card, border: `1px solid ${P.border}`, borderRadius: 6,
                            padding: '8px 12px', color: P.text, fontSize: 12, outline: 'none',
                            resize: 'none', fontFamily: F.ui,
                          }}
                        />
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                      <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>FAILURE / BLOCK REASON</label>
                      <input
                        type="text"
                        placeholder="If failed or blocked, explain why"
                        disabled={isReadOnly}
                        value={failureReason}
                        onChange={e => setFailureReason(e.target.value)}
                        style={{
                          background: P.card, border: `1px solid ${P.border}`, borderRadius: 6,
                          padding: '8px 12px', color: P.text, fontSize: 12, outline: 'none',
                        }}
                      />
                    </div>
                  </div>

                  {/* Verdict Buttons */}
                  {!isReadOnly && (
                    <div style={{ display: 'flex', gap: 8 }}>
                      <Btn
                        variant="primary"
                        onClick={() => handleSaveResult('passed')}
                        style={{
                          flex: 1,
                          background: selectedStep.status === 'passed' ? P.pass : undefined,
                          borderColor: selectedStep.status === 'passed' ? P.pass : undefined,
                          color: selectedStep.status === 'passed' ? '#ffffff' : undefined,
                        }}
                      >
                        <Check size={14} style={{ marginRight: 4 }} /> Pass
                      </Btn>
                      <Btn
                        variant="secondary"
                        onClick={() => handleSaveResult('failed')}
                        style={{
                          flex: 1,
                          background: selectedStep.status === 'failed' ? P.fail : undefined,
                          borderColor: selectedStep.status === 'failed' ? P.fail : undefined,
                          color: selectedStep.status === 'failed' ? '#ffffff' : undefined,
                        }}
                      >
                        <X size={14} style={{ marginRight: 4 }} /> Fail
                      </Btn>
                      <Btn
                        variant="secondary"
                        onClick={() => handleSaveResult('blocked')}
                        style={{
                          flex: 1,
                          background: selectedStep.status === 'blocked' ? P.unclear : undefined,
                          borderColor: selectedStep.status === 'blocked' ? P.unclear : undefined,
                          color: selectedStep.status === 'blocked' ? '#ffffff' : undefined,
                        }}
                      >
                        <Ban size={14} style={{ marginRight: 4 }} /> Block
                      </Btn>
                      <Btn
                        variant="ghost"
                        onClick={() => handleSaveResult('skipped')}
                        style={{
                          flex: 1,
                          background: selectedStep.status === 'skipped' ? P.cardHi : undefined,
                          color: selectedStep.status === 'skipped' ? P.text : undefined,
                        }}
                      >
                        <FastForward size={14} style={{ marginRight: 4 }} /> Skip
                      </Btn>
                    </div>
                  )}

                  {/* Evidence Upload */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 8 }}>
                    <label style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono }}>ATTACH EVIDENCE</label>
                    {!isReadOnly && (
                      <div
                        onClick={() => document.getElementById('manual-evidence-upload')?.click()}
                        style={{
                          border: `1px dashed ${P.border}`, borderRadius: 8, padding: 12,
                          textAlign: 'center', background: P.card, cursor: 'pointer',
                          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                          transition: 'border-color 0.15s, background 0.15s',
                        }}
                        onMouseEnter={e => {
                          e.currentTarget.style.borderColor = P.accent;
                          e.currentTarget.style.background = P.cardHi;
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.borderColor = P.border;
                          e.currentTarget.style.background = P.card;
                        }}
                      >
                        <input
                          id="manual-evidence-upload"
                          type="file"
                          style={{ display: 'none' }}
                          onChange={handleFileUpload}
                        />
                        <Upload size={16} color={P.textMute} />
                        <span style={{ fontSize: 11, color: P.textDim }}>
                          {uploading ? 'Uploading...' : 'Click to select files to upload'}
                        </span>
                      </div>
                    )}
                    {uploadError && (
                      <span style={{ fontSize: 11, color: P.fail }}>{uploadError}</span>
                    )}

                    {/* Step specific evidence */}
                    {stepEvidence.length > 0 && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginTop: 6 }}>
                        {stepEvidence.map(ev => (
                          <EvidenceCard
                            key={ev.id}
                            ev={ev}
                            onClick={ev.evidence_type === 'screenshot' ? () => setPreviewUrl(evidenceDownloadUrl(ev.id)) : undefined}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: P.textMute, fontSize: 13, height: '100%' }}>
                  Select a step from the left timeline to begin execution.
                </div>
              )}

              {/* Finalize button banner */}
              {run.status === 'pending' || run.status === 'running' ? (
                <div style={{
                  marginTop: 'auto', padding: 14, borderRadius: 8,
                  background: canFinalize ? `${P.pass}10` : `${P.unclear}10`,
                  border: `1px solid ${canFinalize ? P.pass : P.unclear}22`,
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
                }}>
                  <div>
                    <div style={{ fontSize: 12, fontWeight: 600, color: canFinalize ? P.pass : P.unclear }}>
                      {canFinalize ? 'Run Ready to Finalize' : 'Required Steps Remaining'}
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim, marginTop: 2 }}>
                      {canFinalize
                        ? 'All required steps have been marked. You can finalize the run.'
                        : `Please review all required steps. Remaining: ${unreviewedRequiredSteps.length}`}
                    </div>
                  </div>
                  <Btn
                    variant="primary"
                    disabled={isDemo || !canFinalize || finishing}
                    title={isDemo ? 'Available in your real workspace. Leave demo to get started.' : undefined}
                    onClick={handleFinalize}
                    data-testid="finalize-run-btn"
                    style={{
                      background: canFinalize ? `linear-gradient(135deg, ${P.pass}, #10b981)` : undefined,
                      borderColor: canFinalize ? '#10b981' : undefined,
                    }}
                  >
                    {finishing ? 'Finalizing...' : 'Finalize Run'}
                  </Btn>
                </div>
              ) : null}
            </div>
          ) : (
            /* Automated Execution Workspace */
            <div style={{ flex: 1, padding: 16, display: 'flex', flexDirection: 'column', gap: 12, overflow: 'hidden' }}>
              {selectedStep && <FailureDetails step={selectedStep} evidence={stepEvidence} />}
              {selectedStep && ['assert_visual_match', 'visual_capture', 'visual_compare'].includes(selectedStep.action_type || '') ? (
                (() => {
                  const currentScreenshotEv = stepEvidence.find(ev => getEvidenceType(ev) === 'screenshot');
                  const visualDiffEv = stepEvidence.find(ev => getEvidenceType(ev) === 'visual_diff');
                  const stepIdx = selectedStep.index;
                  const baselineName = (run?.steps && stepIdx !== undefined ? (run.steps[stepIdx - 1] as any)?.value : undefined) || selectedStep.name;
                  return (
                    <VisualRegressionCard
                      baselineUrl={baselineUrl}
                      currentUrl={currentScreenshotEv ? evidenceDownloadUrl(currentScreenshotEv.id) : undefined}
                      diffUrl={visualDiffEv ? evidenceDownloadUrl(visualDiffEv.id) : undefined}
                      diffRatio={visualDiffEv?.metadata_json?.diff_ratio as number | undefined}
                      threshold={visualDiffEv?.metadata_json?.threshold as number | undefined}
                      isApproving={selectedStep.id ? approvingStepId === selectedStep.id : false}
                      isApproved={selectedStep.id ? !!approvedSteps[selectedStep.id] : false}
                      onApprove={() => {
                        if (currentScreenshotEv && selectedStep.id) {
                          handleApproveBaseline(selectedStep.id, currentScreenshotEv.id, baselineName);
                        } else {
                          alert('No current screenshot available to set as baseline.');
                        }
                      }}
                    />
                  );
                })()
              ) : (
                <LiveAppFrame
                  screenshotUrl={screenshotUrl}
                  platform={run.platform}
                  activeStep={selectedStep}
                  isRunning={isRunning}
                />
              )}

              {selectedStep?.status === 'capability_gap' && (
                <div style={{
                  padding: '12px 16px', borderRadius: 8, background: `${P.unclear}18`,
                  border: `1px solid ${P.unclear}33`, display: 'flex', flexDirection: 'column', gap: 4
                }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: P.unclear, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertTriangle size={14} /> CAPABILITY GAP DETECTED
                  </div>
                  <div style={{ fontSize: 11, color: P.textDim }}>
                    {(selectedStep as any).notes || 'This step requires capabilities not currently available.'}
                  </div>
                </div>
              )}

              {selectedStep?.status === 'failed' && (
                <div style={{
                  padding: '12px 16px', borderRadius: 8, background: `${P.fail}18`,
                  border: `1px solid ${P.fail}33`, display: 'flex', flexDirection: 'column', gap: 4
                }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: P.fail, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertTriangle size={14} /> STEP EXECUTION FAILED
                  </div>
                  <div style={{ fontSize: 11, color: P.textDim }}>
                    {(selectedStep as any).notes || selectedStep.error || 'The assertion or interaction failed during execution.'}
                  </div>
                </div>
              )}

              {selectedStep && (selectedStep as any).warning && (
                <div style={{
                  padding: '12px 16px', borderRadius: 8, background: `${P.unclear}18`,
                  border: `1px solid ${P.unclear}33`, display: 'flex', flexDirection: 'column', gap: 4
                }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: P.unclear, display: 'flex', alignItems: 'center', gap: 6 }}>
                    <AlertTriangle size={14} /> {['check_accessibility', 'assert_accessibility', 'accessibility_scan', 'assert_no_critical_a11y_violations', 'assert_no_a11y_violations'].includes(selectedStep.action_type || '') ? 'ACCESSIBILITY WARNING' : ['passive_security_check', 'assert_no_critical_security_findings', 'assert_security_headers_present', 'assert_cookie_flags_secure'].includes(selectedStep.action_type || '') ? 'SECURITY WARNING' : 'PERFORMANCE WARNING'}
                  </div>
                  <div style={{ fontSize: 11, color: P.textDim }}>
                    {selectedStep.notes || 'Warning threshold exceeded.'}
                  </div>
                </div>
              )}

              {selectedStep && (
                <Card>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
                      <div style={{ fontSize: 13, fontWeight: 600, color: P.text }}>
                        Step {selectedStep.index}: {selectedStep.name}
                      </div>
                      {selectedStep.action_type && (
                        <span style={{ fontSize: 9, color: P.accent, fontFamily: F.mono, textTransform: 'uppercase' }}>
                          {selectedStep.action_type}
                        </span>
                      )}
                    </div>
                    {(selectedStep.method || selectedStep.url || selectedStep.status_code != null || selectedStep.response_time_ms != null) && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                        {selectedStep.method && <div style={{ fontSize: 11, color: P.textDim }}><span style={{ color: P.textMute, fontFamily: F.mono }}>method:</span> {selectedStep.method}</div>}
                        {selectedStep.status_code != null && <div style={{ fontSize: 11, color: P.textDim }}><span style={{ color: P.textMute, fontFamily: F.mono }}>status:</span> {selectedStep.status_code}</div>}
                        {selectedStep.url && <div style={{ gridColumn: '1 / -1', fontSize: 11, color: P.textDim, wordBreak: 'break-word' }}><span style={{ color: P.textMute, fontFamily: F.mono }}>url:</span> {selectedStep.url}</div>}
                        {selectedStep.response_time_ms != null && <div style={{ fontSize: 11, color: P.textDim }}><span style={{ color: P.textMute, fontFamily: F.mono }}>latency_ms:</span> {selectedStep.response_time_ms}</div>}
                        {selectedStep.assertion_result != null && <div style={{ fontSize: 11, color: selectedStep.assertion_result ? P.pass : P.fail }}><span style={{ color: P.textMute, fontFamily: F.mono }}>assertion_result:</span> {selectedStep.assertion_result ? 'passed' : 'failed'}</div>}
                      </div>
                    )}
                    {((selectedStep as any).budget_ms != null || (selectedStep as any).warn_ms != null || (selectedStep as any).metric_name) && (
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, borderTop: `1px solid ${P.border}`, paddingTop: 8, marginTop: 4 }}>
                        {(selectedStep as any).budget_ms != null && <div style={{ fontSize: 11, color: P.textDim }}><span style={{ color: P.textMute, fontFamily: F.mono }}>budget_ms:</span> {(selectedStep as any).budget_ms}</div>}
                        {(selectedStep as any).warn_ms != null && <div style={{ fontSize: 11, color: P.textDim }}><span style={{ color: P.textMute, fontFamily: F.mono }}>warn_ms:</span> {(selectedStep as any).warn_ms}</div>}
                        {(selectedStep as any).metric_name && <div style={{ gridColumn: '1 / -1', fontSize: 11, color: P.textDim }}><span style={{ color: P.textMute, fontFamily: F.mono }}>metric_name:</span> {(selectedStep as any).metric_name}</div>}
                      </div>
                    )}
                    {selectedStep.failure_reason && (
                      <div style={{ fontSize: 11, color: P.fail }}>
                        {selectedStep.failure_reason}
                      </div>
                    )}
                    {selectedStep.notes && (
                      <div style={{ fontSize: 11, color: P.textDim }}>
                        {selectedStep.notes}
                      </div>
                    )}
                  </div>
                </Card>
              )}

              {metrics && <PerformanceMetricsCard metrics={metrics} />}

              {a11yResult && <AccessibilityViolationsCard a11yResult={a11yResult} />}

              {securityFindings.length > 0 && <SecurityFindingsCard findings={securityFindings} />}

              {displayedSteps.some(step => step.status === 'failed' && (step.notes || step.failure_reason)) && (
                <Card>
                  <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                    textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                    Failed Steps
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    {displayedSteps.filter(step => step.status === 'failed' && (step.notes || step.failure_reason)).map(step => (
                      <div key={step.step_id || step.index} style={{ fontSize: 11, color: P.textDim }}>
                        <span style={{ color: P.textMute, fontFamily: F.mono }}>step {step.index}:</span>{' '}
                        {step.failure_reason || step.notes || '—'}
                      </div>
                    ))}
                  </div>
                </Card>
              )}
            </div>
          )}

          {/* Evidence for selected step (non-manual mode only, manual evidence is shown inline) */}
          {!isManual && selectedStep && stepEvidence.length > 0 && (
            <div style={{ padding: '0 16px 12px', borderTop: `1px solid ${P.border}`,
              maxHeight: 200, overflowY: 'auto' }}>
              <div style={{ fontSize: 10, color: P.textMute, fontFamily: "'JetBrains Mono',monospace",
                textTransform: 'uppercase', letterSpacing: '0.06em', padding: '8px 0 6px' }}>
                EVIDENCE · {stepEvidence.length}
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {stepEvidence.map(ev => {
                  const metadata = ev.metadata_json ?? {};
                  const evidenceType = getEvidenceType(ev);
                  return (
                    <div key={ev.id} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                      <EvidenceCard
                        ev={ev}
                        onClick={evidenceType === 'screenshot' ? () => setPreviewUrl(evidenceDownloadUrl(ev.id)) : undefined}
                      />
                      {(evidenceType === 'api_request' || evidenceType === 'api_response' || evidenceType === 'api_assertion') && (
                        <div style={{
                          padding: '8px 10px', borderRadius: 8, background: P.cardHi,
                          border: `1px solid ${P.border}`, fontSize: 11, color: P.textDim,
                        }}>
                          <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono,
                            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
                            {evidenceType.replace(/_/g, ' ')}
                          </div>
                          {'method' in metadata && <div><span style={{ color: P.textMute, fontFamily: F.mono }}>method:</span> {String(metadata.method)}</div>}
                          {'url' in metadata && <div style={{ wordBreak: 'break-word' }}><span style={{ color: P.textMute, fontFamily: F.mono }}>url:</span> {String(metadata.url)}</div>}
                          {'status_code' in metadata && <div><span style={{ color: P.textMute, fontFamily: F.mono }}>status_code:</span> {String(metadata.status_code)}</div>}
                          {'response_time_ms' in metadata && <div><span style={{ color: P.textMute, fontFamily: F.mono }}>response_time_ms:</span> {String(metadata.response_time_ms)}</div>}
                          {'headers' in metadata && (
                            <pre style={{ margin: '6px 0 0', whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontFamily: F.mono, color: P.text }}>
                              {formatMetadata(metadata.headers)}
                            </pre>
                          )}
                          {'details' in metadata && <div style={{ color: P.fail }}>{String(metadata.details)}</div>}
                          {'passed' in metadata && <div><span style={{ color: P.textMute, fontFamily: F.mono }}>passed:</span> {String(metadata.passed)}</div>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        </div>

        {/* Right: evidence hero and verdict context */}
        <div className="run-evidence-column" style={{ borderLeft: `1px solid ${P.border}`,
          overflowY: 'auto', padding: 12, background: P.surface }}>
          {evidenceError ? (
            <div role="alert" style={{ marginBottom: 12, padding: 12, borderRadius: 8, border: `1px solid ${P.fail}44`, background: P.failSoft, color: P.fail, fontSize: 11 }}>
              Evidence could not be loaded.{' '}
              <button type="button" onClick={refetchEvidence} style={{ border: 0, padding: 0, background: 'transparent', color: P.text, textDecoration: 'underline', cursor: 'pointer' }}>Retry</button>
            </div>
          ) : (
            <EvidencePanel
              run={run}
              step={selectedStep}
              evidence={selectedStep ? stepEvidence : evidence ?? []}
              onManualVerdict={isManual && !isReadOnly ? (status) => handleSaveResult(status) : undefined}
            />
          )}

          <div style={{ marginTop: 12 }}>
            <VerdictPanel run={run} selectedStep={selectedStep} />
          </div>

          <div style={{ marginTop: 12 }}>
            <Card>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div style={{ fontSize: 10, color: P.textMute, fontFamily: F.mono, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                    AI Evaluation Notes
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    <span style={{
                      fontSize: 9, fontWeight: 700, fontFamily: F.mono,
                      color: P.unclear, background: `${P.unclear}15`, border: `1px solid ${P.unclear}33`,
                      borderRadius: 4, padding: '2px 6px'
                    }}>
                      AI Draft — Non-Authoritative
                    </span>
                  </div>
                  <div style={{ fontSize: 11, color: P.textDim }}>
                    This does not change the actual run verdict.
                  </div>
                </div>

                {aiError && (
                  <div style={{
                    padding: '8px 10px', borderRadius: 8, background: `${P.fail}18`,
                    border: `1px solid ${P.fail}33`, fontSize: 11, color: P.fail
                  }}>
                    {aiError}
                  </div>
                )}

                {aiNotes.length === 0 && !aiError && (
                  <div style={{ fontSize: 11, color: P.textMute }}>
                    {aiLoading ? 'Loading AI notes…' : 'No AI draft notes yet.'}
                  </div>
                )}

                {aiNotes.map((note) => (
                  <div key={note.evaluation_id} style={{
                    display: 'flex', flexDirection: 'column', gap: 8, paddingTop: 8,
                    borderTop: `1px solid ${P.border}`
                  }}>
                    <div style={{ fontSize: 11, color: P.text }}>
                      {note.verdict_assessment}
                    </div>
                    {note.suggested_verdict && (
                      <div style={{ fontSize: 11, color: P.textDim }}>
                        <span style={{ color: P.textMute, fontFamily: F.mono }}>suggested_verdict:</span> {note.suggested_verdict}
                      </div>
                    )}
                    {note.confidence != null && (
                      <div style={{ fontSize: 11, color: P.textDim }}>
                        <span style={{ color: P.textMute, fontFamily: F.mono }}>confidence:</span> {Math.round(note.confidence * 100)}%
                      </div>
                    )}
                    {note.summary && (
                      <div style={{ fontSize: 11, color: P.textDim }}>
                        <span style={{ color: P.textMute, fontFamily: F.mono }}>summary:</span> {note.summary}
                      </div>
                    )}
                    {note.rationale && (
                      <div style={{ fontSize: 11, color: P.textDim }}>
                        <span style={{ color: P.textMute, fontFamily: F.mono }}>rationale:</span> {note.rationale}
                      </div>
                    )}
                    <div style={{ fontSize: 11, color: P.textDim }}>
                      <span style={{ color: P.textMute, fontFamily: F.mono }}>evidence_used:</span> {renderStringList(note.evidence_used)}
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim }}>
                      <span style={{ color: P.textMute, fontFamily: F.mono }}>missing_evidence:</span> {renderStringList(note.missing_evidence)}
                    </div>
                    <div style={{ fontSize: 11, color: P.textDim }}>
                      <span style={{ color: P.textMute, fontFamily: F.mono }}>risk_flags:</span> {renderStringList(note.risk_flags)}
                    </div>
                    {note.generation_source && (
                      <div style={{ fontSize: 11, color: P.textDim }}>
                        <span style={{ color: P.textMute, fontFamily: F.mono }}>generation_source:</span> {note.generation_source}
                      </div>
                    )}
                    {note.created_at && (
                      <div style={{ fontSize: 11, color: P.textDim }}>
                        <span style={{ color: P.textMute, fontFamily: F.mono }}>created_at:</span> {new Date(note.created_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </Card>
          </div>

          <div style={{ marginTop: 12 }}>
            <AIRootCauseSuggestions
              runId={run.id}
              runStatus={run.status}
              hasFailureSignal={hasRootCauseFailureSignal}
              isDemo={isDemo}
              backendAvailable={!runError}
              onSelectStep={(stepId) => {
                const step = displayedSteps.find(item => item.step_id === stepId || item.id === stepId);
                if (step) setSelectedStep(step);
              }}
            />
          </div>

          <div style={{ marginTop: 12 }}>
            <RunHistoryPanel
              runId={run.id}
              onSelectStep={(stepId) => {
                const step = displayedSteps.find(item => item.step_id === stepId || item.id === stepId);
                if (step) setSelectedStep(step);
              }}
            />
          </div>

          <div style={{ marginTop: 12 }}>
            <RunComparisonPanel run={run} backendAvailable={!runError} />
          </div>

          {/* All evidence */}
          {evidence && evidence.length > 0 && !selectedStep && (
            <div style={{ marginTop: 12 }}>
              <div style={{ fontSize: 10, color: P.textMute, fontFamily: "'JetBrains Mono',monospace",
                textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
                ALL EVIDENCE
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {evidence.slice(0, 6).map(ev => (
                  <EvidenceCard
                    key={ev.id}
                    ev={ev}
                    onClick={getEvidenceType(ev) === 'screenshot' ? () => setPreviewUrl(evidenceDownloadUrl(ev.id)) : undefined}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Bottom: Event stream */}
      <EventStreamDrawer
        durableEvents={durableEvents}
        liveEvents={events}
        connected={connected}
        active={isRunning}
        error={streamError}
        defaultOpen
      />

      {/* Screenshot Preview Modal Overlay */}
      {previewUrl && (
        <div
          onClick={() => setPreviewUrl(null)}
          style={{
            position: 'fixed',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
            padding: 24,
            backdropFilter: 'blur(4px)',
          }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{
              position: 'relative',
              maxWidth: '90%',
              maxHeight: '90%',
              background: P.surface,
              border: `1px solid ${P.border}`,
              borderRadius: 12,
              padding: 6,
              boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            <button
              onClick={() => setPreviewUrl(null)}
              style={{
                position: 'absolute',
                top: -12,
                right: -12,
                width: 28,
                height: 28,
                borderRadius: '50%',
                background: P.surface,
                border: `1px solid ${P.border}`,
                color: P.text,
                fontSize: 14,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
              }}
            >
              &times;
            </button>
            <img
              src={previewUrl}
              alt="Screenshot Preview"
              style={{
                maxWidth: '100%',
                maxHeight: '80vh',
                borderRadius: 8,
                objectFit: 'contain',
              }}
            />
          </div>
        </div>
      )}
    </AppShell>
  );
}
