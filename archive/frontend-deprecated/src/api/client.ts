/**
 * API client for the Inspectra product backend.
 * All calls go to /api/* which Vite proxies to 127.0.0.1:8765.
 * No credentials, no secrets in requests.
 */
import type {
  AppTarget, AppTargetCreate, AppTargetUpdate,
  ConnectorsResponse, DashboardSummary, EvidenceFile,
  LiveRunRecord, PermissionRecord, ProductSetting,
  Project, ProjectCreate, ProjectUpdate,
  ReportRecord, RuntimeDoctorReport,
  ValidationPack, ValidationPackCreate, ValidationPackUpdate,
} from './types';

const BASE = '/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
  };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const resp = await fetch(`${BASE}${path}`, opts);
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try { detail = (await resp.json()).detail || detail; } catch { /* ignore */ }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

const get  = <T>(path: string)                 => req<T>('GET',    path);
const post = <T>(path: string, body?: unknown) => req<T>('POST',   path, body);
const patch= <T>(path: string, body?: unknown) => req<T>('PATCH',  path, body);
const del  = (path: string)                    => req<void>('DELETE', path);

// ── Dashboard ─────────────────────────────────────────────────────────────────

export const getDashboard = () => get<DashboardSummary>('/dashboard');

// ── Projects ──────────────────────────────────────────────────────────────────

export const listProjects    = ()                                      => get<Project[]>('/projects');
export const getProject      = (id: string)                            => get<Project>(`/projects/${id}`);
export const createProject   = (body: ProjectCreate)                   => post<Project>('/projects', body);
export const updateProject   = (id: string, body: ProjectUpdate)       => patch<Project>(`/projects/${id}`, body);
export const deleteProject   = (id: string)                            => del(`/projects/${id}`);

// ── App targets ───────────────────────────────────────────────────────────────

export const listApps    = (projectId?: string) =>
  get<AppTarget[]>(`/apps${projectId ? `?project_id=${projectId}` : ''}`);
export const getApp      = (id: string)                          => get<AppTarget>(`/apps/${id}`);
export const createApp   = (body: AppTargetCreate)               => post<AppTarget>('/apps', body);
export const updateApp   = (id: string, body: AppTargetUpdate)   => patch<AppTarget>(`/apps/${id}`, body);
export const deleteApp   = (id: string)                          => del(`/apps/${id}`);

// ── Validation packs ──────────────────────────────────────────────────────────

export const listPacks   = (projectId?: string) =>
  get<ValidationPack[]>(`/validation-packs${projectId ? `?project_id=${projectId}` : ''}`);
export const getPack     = (id: string)                              => get<ValidationPack>(`/validation-packs/${id}`);
export const createPack  = (body: ValidationPackCreate)              => post<ValidationPack>('/validation-packs', body);
export const updatePack  = (id: string, body: ValidationPackUpdate)  => patch<ValidationPack>(`/validation-packs/${id}`, body);
export const deletePack  = (id: string)                              => del(`/validation-packs/${id}`);
export const runPack     = (packId: string, appTargetId: string)     =>
  post<LiveRunRecord>(`/validation-packs/${packId}/run`, { app_target_id: appTargetId });

// ── Live runs ─────────────────────────────────────────────────────────────────

export const listRuns    = (packId?: string, limit = 50) =>
  get<LiveRunRecord[]>(`/runs?limit=${limit}${packId ? `&pack_id=${packId}` : ''}`);
export const getRun      = (id: string)  => get<LiveRunRecord>(`/runs/${id}`);
export const cancelRun   = (id: string)  => del(`/runs/${id}`);

// ── Permissions ───────────────────────────────────────────────────────────────

export const listPermissions     = (runId?: string, status?: string) => {
  const params = new URLSearchParams();
  if (runId) params.set('run_id', runId);
  if (status) params.set('status', status);
  const qs = params.toString();
  return get<PermissionRecord[]>(`/permissions${qs ? `?${qs}` : ''}`);
};
export const approvePermission   = (id: string, reason?: string) =>
  post<PermissionRecord>(`/permissions/${id}/approve`, { approved: true, reason });
export const denyPermission      = (id: string, reason?: string) =>
  post<PermissionRecord>(`/permissions/${id}/deny`, { approved: false, reason });

// ── Evidence ──────────────────────────────────────────────────────────────────

export const listEvidence  = (runId?: string) =>
  get<EvidenceFile[]>(`/evidence${runId ? `?run_id=${runId}` : ''}`);
export const getEvidence   = (id: string) => get<EvidenceFile>(`/evidence/${id}`);
export const downloadEvidenceUrl = (id: string) => `${BASE}/evidence/${id}/download`;

// ── Reports ───────────────────────────────────────────────────────────────────

export const listReports   = (runId?: string) =>
  get<ReportRecord[]>(`/reports${runId ? `?run_id=${runId}` : ''}`);
export const getReport     = (id: string) => get<ReportRecord>(`/reports/${id}`);
export const exportReportUrl = (id: string) => `${BASE}/reports/${id}/export`;

// ── Connectors ────────────────────────────────────────────────────────────────

export const getConnectors = () => get<ConnectorsResponse>('/connectors');

// ── Runtime Doctor ────────────────────────────────────────────────────────────

export const getRuntimeDoctor = (appTypes?: string[]) => {
  const qs = appTypes?.map(t => `app_types=${encodeURIComponent(t)}`).join('&') || '';
  return get<RuntimeDoctorReport>(`/runtime-doctor${qs ? `?${qs}` : ''}`);
};

// ── Settings ──────────────────────────────────────────────────────────────────

export const listSettings  = ()                           => get<ProductSetting[]>('/settings');
export const getSetting    = (key: string)                => get<ProductSetting>(`/settings/${key}`);
export const setSetting    = (key: string, value: string) =>
  patch<ProductSetting>(`/settings/${key}`, { value });

export { ApiError };
