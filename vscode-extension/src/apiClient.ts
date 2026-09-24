/**
 * apiClient.ts - HTTP client for the Inspectra local dashboard API.
 *
 * All methods are read-only GET requests. The dashboard URL is read from
 * VS Code configuration so users can change the port without editing code.
 */
import * as vscode from "vscode";

export interface Finding {
  id: string;
  title: string;
  severity: string;
  category: string;
  description?: string;
  evidence?: unknown;
  tags?: string[];
}

export interface RiskReport {
  overall_score?: number;
  score?: number;
  risk_level?: string;
  level?: string;
  summary?: string;
}

export interface AuditSummary {
  status?: string;
  target_path?: string;
  target?: string;
  profile?: string;
  phases_executed?: string[];
}

export interface CorpusRuntimeStatus {
  detected: boolean;
  healthy: boolean;
  base_url?: string | null;
  source?: string | null;
}

export interface CorpusConnectionStatus {
  state: "connected" | "pending_approval" | "denied" | "disconnected";
  connected: boolean;
  pending_approval: boolean;
  denied: boolean;
  disconnected: boolean;
  workspace_name?: string | null;
  trust_level?: string | null;
  permissions_granted: string[];
  reason?: string | null;
}

export interface ArtifactEntry {
  name: string;
  agent: string;
  saved_at: string;
  size_bytes: number;
}

function getDashboardUrl(): string {
  const cfg = vscode.workspace.getConfiguration("inspectra");
  return (cfg.get<string>("dashboardUrl") ?? "http://127.0.0.1:8765").replace(/\/$/, "");
}

async function get<T>(path: string): Promise<T | null> {
  const url = `${getDashboardUrl()}${path}`;
  try {
    const resp = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!resp.ok) {
      return null;
    }
    return (await resp.json()) as T;
  } catch {
    return null;
  }
}

export async function fetchFindings(): Promise<Finding[]> {
  return (await get<Finding[]>("/api/findings")) ?? [];
}

export async function fetchRisk(): Promise<RiskReport> {
  return (await get<RiskReport>("/api/risk")) ?? {};
}

export async function fetchSummary(): Promise<AuditSummary> {
  return (await get<AuditSummary>("/api/summary")) ?? {};
}

export async function fetchArtifacts(): Promise<ArtifactEntry[]> {
  return (await get<ArtifactEntry[]>("/api/artifacts")) ?? [];
}

export async function checkHealth(): Promise<boolean> {
  const result = await get<{ status: string }>("/health");
  return result?.status === "ok";
}

export async function fetchCorpusRuntime(): Promise<CorpusRuntimeStatus> {
  return (await get<CorpusRuntimeStatus>("/api/corpus/runtime")) ?? {
    detected: false,
    healthy: false,
  };
}

export async function fetchCorpusStatus(): Promise<CorpusConnectionStatus> {
  return (await get<CorpusConnectionStatus>("/api/corpus/status")) ?? {
    state: "disconnected",
    connected: false,
    pending_approval: false,
    denied: false,
    disconnected: true,
    workspace_name: "AI Engineering Workspace",
    trust_level: null,
    permissions_granted: [],
  };
}

export async function requestCorpusConnection(): Promise<boolean> {
  const response = await fetch(`${getDashboardUrl()}/api/corpus/request`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  return response.ok;
}

export async function reconnectCorpusWithToken(): Promise<boolean> {
  const response = await fetch(`${getDashboardUrl()}/api/corpus/reconnect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    return false;
  }
  const payload = (await response.json()) as { connected?: boolean };
  return payload.connected === true;
}

export async function disconnectCorpus(): Promise<boolean> {
  const response = await fetch(`${getDashboardUrl()}/api/corpus/disconnect`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    return false;
  }
  const payload = (await response.json()) as { disconnected?: boolean };
  return payload.disconnected === true;
}
