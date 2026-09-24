/**
 * Inspectra API client.
 * - Typed fetch wrapper with timeout + error handling
 * - Tracks backend connection status
 * - Never substitutes sample data for backend responses
 * - Never logs secrets
 */
import type { BackendStatus, AIEvaluationNote, AIRootCauseSuggestionBatch, RunHistoryResponse, RunComparisonResponse } from '../types/api';
import { isDemoPath } from '../state/workspaceMode';

const API_BASE = '/api';
const TIMEOUT_MS = 15_000;

// ── Connection state (module-level) ──────────────────────────────────────────

let _backendStatus: BackendStatus = 'offline';
let _statusListeners: Array<(s: BackendStatus) => void> = [];

export function getBackendStatus(): BackendStatus { return _backendStatus; }
export function onBackendStatus(fn: (s: BackendStatus) => void) {
  _statusListeners.push(fn);
  return () => { _statusListeners = _statusListeners.filter(l => l !== fn); };
}
function setStatus(s: BackendStatus) {
  if (_backendStatus !== s) {
    _backendStatus = s;
    _statusListeners.forEach(l => l(s));
  }
}

// ── Errors ────────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

export function assertRealWorkspace(): void {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) {
    throw new ApiError(0, 'Requests are disabled in the read-only demo workspace.');
  }
}

// ── Core fetch ────────────────────────────────────────────────────────────────

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  assertRealWorkspace();

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

  try {
    const opts: RequestInit = {
      method,
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      signal: controller.signal,
    };
    if (body !== undefined) opts.body = JSON.stringify(body);
    const resp = await fetch(`${API_BASE}${path}`, opts);

    if (resp.ok || resp.status < 500) setStatus('online');

    if (!resp.ok) {
      let detail = `${resp.status} ${resp.statusText}`;
      try { detail = (await resp.json()).detail || detail; } catch { /* ignore */ }
      if (resp.status >= 500) setStatus('degraded');
      throw new ApiError(resp.status, detail);
    }
    if (resp.status === 204) return undefined as T;
    return resp.json() as Promise<T>;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if ((err as Error).name === 'AbortError') {
      setStatus('degraded');
      throw new ApiError(0, 'Request timed out');
    }
    setStatus('offline');
    throw new ApiError(0, (err as Error).message || 'Network error');
  } finally {
    clearTimeout(timer);
  }
}

export const get  = <T>(path: string)                 => req<T>('GET',    path);
export const post = <T>(path: string, body?: unknown) => req<T>('POST',   path, body);
export const patch= <T>(path: string, body?: unknown) => req<T>('PATCH',  path, body);
export const del  = (path: string)                    => req<void>('DELETE', path);

// ── Health check ──────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<BackendStatus> {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) return 'offline';
  try {
    const r = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(3000) });
    // The health route is a constant local liveness response. In Vite dev mode,
    // an unreachable FastAPI target is surfaced by the proxy as HTTP 5xx.
    const s: BackendStatus = r.ok ? 'online' : r.status >= 500 ? 'offline' : 'degraded';
    setStatus(s);
    return s;
  } catch {
    setStatus('offline');
    return 'offline';
  }
}

// ── SSE helper ────────────────────────────────────────────────────────────────

export function createRunStream(runId: string): EventSource {
  assertRealWorkspace();
  return new EventSource(`${API_BASE}/runs/${encodeURIComponent(runId)}/stream`);
}

// ── Evidence download URL (safe, no auto-open) ────────────────────────────────

export function evidenceDownloadUrl(id: string): string {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) return 'data:,';
  return `${API_BASE}/evidence/${encodeURIComponent(id)}/download`;
}

export function runEvidenceZipUrl(runId: string): string {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) return 'data:,';
  return `${API_BASE}/runs/${encodeURIComponent(runId)}/evidence.zip`;
}

export function baselineDownloadUrl(id: string): string {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) return 'data:,';
  return `${API_BASE}/baselines/${encodeURIComponent(id)}/download`;
}

export function reportExportUrl(id: string): string {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) return 'data:application/json,{}';
  return `${API_BASE}/reports/${encodeURIComponent(id)}/export`;
}

export type RunReportFormat = 'html' | 'pdf' | 'junit' | 'sarif';

export function runReportDownloadUrl(runId: string, format: RunReportFormat): string {
  if (typeof window !== 'undefined' && isDemoPath(window.location.pathname)) return 'data:,';
  return `${API_BASE}/runs/${encodeURIComponent(runId)}/report?format=${format}`;
}

export function runReportFilename(runId: string, format: RunReportFormat): string {
  const extension: Record<RunReportFormat, string> = {
    html: 'html',
    pdf: 'pdf',
    junit: 'junit.xml',
    sarif: 'sarif.json',
  };
  const safeRunId = runId.replace(/[^A-Za-z0-9._-]/g, '-').slice(0, 120) || 'run';
  return `inspectra-run-${safeRunId}.${extension[format]}`;
}

/** Generate a summary report from a completed run. */
export function generateReport(runId: string) {
  return post<import('../types/api').ReportRecord>(`/runs/${encodeURIComponent(runId)}/report/generate`);
}

/** Create a retest run scoped to failed steps. */
export function retestFailed(runId: string) {
  return post<import('../types/api').LiveRunRecord>(`/runs/${encodeURIComponent(runId)}/retest-failed`);
}

type LegacyRetestComparison = {
    run_id: string;
    parent_run_id: string;
    comparison: Array<{ step: number; prev_status: string; curr_status: string; change: string }>;
    summary: { fixed: number; regressed: number; unchanged: number; changed: number; total: number };
};

/** Existing retest call remains compatible; explicit pairs use the new API. */
export function getRunComparison(runId: string): Promise<LegacyRetestComparison>;
export function getRunComparison(runId: string, baselineRunId: string): Promise<RunComparisonResponse>;
export function getRunComparison(runId: string, baselineRunId?: string): Promise<LegacyRetestComparison | RunComparisonResponse> {
  if (baselineRunId !== undefined) {
    return get<RunComparisonResponse>(`/runs/${encodeURIComponent(runId)}/compare?baseline_run_id=${encodeURIComponent(baselineRunId)}`);
  }
  return get<LegacyRetestComparison>(`/runs/${encodeURIComponent(runId)}/comparison`);
}

/** Fetch bounded deterministic history for one run's exact pack and target. */
export function getRunHistory(runId: string, limit = 20) {
  return get<RunHistoryResponse>(
    `/runs/${encodeURIComponent(runId)}/history?limit=${encodeURIComponent(String(limit))}`,
  );
}

/** Trigger AI draft evaluation for a finished run's evidence. */
export function evaluateRunEvidence(runId: string) {
  return post<AIEvaluationNote[] | { notes: AIEvaluationNote[] }>(`/runs/${encodeURIComponent(runId)}/evaluate-ai`);
}

/** Fetch AI draft evaluation notes for a run. */
export function getRunEvaluation(runId: string) {
  return get<AIEvaluationNote[] | { notes: AIEvaluationNote[] }>(`/runs/${encodeURIComponent(runId)}/evaluation-ai`);
}

/** Fetch the latest persisted draft root-cause analysis for a run. */
export function getRunRootCauseSuggestions(runId: string) {
  return get<AIRootCauseSuggestionBatch>(`/runs/${encodeURIComponent(runId)}/root-cause-ai`);
}

/** Explicitly request a new draft root-cause analysis. Never called automatically. */
export function generateRunRootCauseSuggestions(runId: string, stepId?: string) {
  return post<AIRootCauseSuggestionBatch>(
    `/runs/${encodeURIComponent(runId)}/root-cause-ai`,
    stepId ? { step_id: stepId } : {},
  );
}
