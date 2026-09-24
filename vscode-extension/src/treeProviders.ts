/**
 * treeProviders.ts - VS Code TreeDataProvider implementations for
 * the Inspectra sidebar views (Findings, Risk & Summary, Corpus).
 */
import * as vscode from "vscode";
import {
  fetchFindings,
  fetchRisk,
  fetchSummary,
  fetchCorpusRuntime,
  fetchCorpusStatus,
  Finding,
  RiskReport,
  AuditSummary,
  CorpusConnectionStatus,
  CorpusRuntimeStatus,
} from "./apiClient";

// ── shared node type ──────────────────────────────────────────────────────────

export class InfoItem extends vscode.TreeItem {
  constructor(
    label: string,
    description?: string,
    collapsibleState = vscode.TreeItemCollapsibleState.None,
    public readonly findingData?: Finding
  ) {
    super(label, collapsibleState);
    if (description) this.description = description;
  }
}

// ── findings tree ─────────────────────────────────────────────────────────────

const SEV_ICON: Record<string, string> = {
  critical: "error",
  high: "warning",
  medium: "info",
  low: "pass",
  info: "circle-outline",
};

export class FindingsProvider implements vscode.TreeDataProvider<InfoItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<InfoItem | undefined | null>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private findings: Finding[] = [];
  private loading = false;

  async refresh(): Promise<void> {
    this.loading = true;
    this._onDidChangeTreeData.fire(null);
    this.findings = await fetchFindings();
    this.loading = false;
    this._onDidChangeTreeData.fire(null);
  }

  getTreeItem(element: InfoItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: InfoItem): Promise<InfoItem[]> {
    if (element) return [];

    if (this.loading) {
      return [new InfoItem("Loading findings…")];
    }
    if (this.findings.length === 0) {
      return [new InfoItem("No findings — run an audit first")];
    }

    return this.findings.map((f) => {
      const sev = (f.severity ?? "unknown").toLowerCase();
      const item = new InfoItem(
        f.title || f.id || "(untitled)",
        sev.toUpperCase(),
        vscode.TreeItemCollapsibleState.None,
        f
      );
      const icon = SEV_ICON[sev] ?? "circle-outline";
      item.iconPath = new vscode.ThemeIcon(icon);
      item.tooltip = [
        `ID: ${f.id ?? "—"}`,
        `Severity: ${f.severity ?? "—"}`,
        `Category: ${f.category ?? "—"}`,
        f.description ? `\n${f.description}` : "",
      ]
        .filter(Boolean)
        .join("\n");
      item.command = {
        command: "inspectra.showFindingDetail",
        title: "Show Detail",
        arguments: [f],
      };
      return item;
    });
  }
}

// ── risk / summary tree ───────────────────────────────────────────────────────

export class RiskProvider implements vscode.TreeDataProvider<InfoItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<InfoItem | undefined | null>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private risk: RiskReport = {};
  private summary: AuditSummary = {};

  async refresh(): Promise<void> {
    [this.risk, this.summary] = await Promise.all([fetchRisk(), fetchSummary()]);
    this._onDidChangeTreeData.fire(null);
  }

  getTreeItem(element: InfoItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: InfoItem): Promise<InfoItem[]> {
    if (element) return [];

    const score = this.risk.overall_score ?? this.risk.score ?? "—";
    const level = this.risk.risk_level ?? this.risk.level ?? "—";
    const status = this.summary.status ?? "—";
    const target = this.summary.target_path ?? this.summary.target ?? "—";
    const profile = this.summary.profile ?? "—";
    const phases = (this.summary.phases_executed ?? []).join(", ") || "—";

    return [
      new InfoItem("Status", String(status)),
      new InfoItem("Risk Level", String(level)),
      new InfoItem("Risk Score", String(score)),
      new InfoItem("Profile", String(profile)),
      new InfoItem("Target", String(target).slice(-60)),
      new InfoItem("Phases", phases),
    ];
  }
}

// ── corpus integration tree ──────────────────────────────────────────────────

export class CorpusProvider implements vscode.TreeDataProvider<InfoItem> {
  private _onDidChangeTreeData = new vscode.EventEmitter<InfoItem | undefined | null>();
  readonly onDidChangeTreeData = this._onDidChangeTreeData.event;

  private runtime: CorpusRuntimeStatus = { detected: false, healthy: false };
  private status: CorpusConnectionStatus = {
    state: "disconnected",
    connected: false,
    pending_approval: false,
    denied: false,
    disconnected: true,
    permissions_granted: [],
  };

  async refresh(): Promise<void> {
    [this.runtime, this.status] = await Promise.all([fetchCorpusRuntime(), fetchCorpusStatus()]);
    this._onDidChangeTreeData.fire(null);
  }

  getTreeItem(element: InfoItem): vscode.TreeItem {
    return element;
  }

  async getChildren(element?: InfoItem): Promise<InfoItem[]> {
    if (element) return [];

    const items: InfoItem[] = [];
    const runtimeLabel = this.runtime.detected && this.runtime.healthy
      ? "Corpus runtime detected"
      : "Corpus runtime unavailable";
    items.push(new InfoItem("Runtime", runtimeLabel));

    if (this.status.connected) {
      items.push(new InfoItem("Corpus", "Connected"));
      items.push(new InfoItem("Workspace", this.status.workspace_name ?? "AI Engineering Workspace"));
      items.push(new InfoItem("Trust Level", this.status.trust_level ?? "STANDARD"));
      for (const permission of this.status.permissions_granted) {
        items.push(new InfoItem(`\u2713 ${permission}`));
      }
      const disconnect = new InfoItem("Disconnect", "Click to revoke session");
      disconnect.command = { command: "inspectra.corpusDisconnect", title: "Disconnect" };
      disconnect.iconPath = new vscode.ThemeIcon("debug-disconnect");
      items.push(disconnect);
      return items;
    }

    if (this.status.pending_approval) {
      items.push(new InfoItem("Corpus", "Pending Approval"));
      items.push(new InfoItem("Authorization", "Waiting for approval..."));
      const check = new InfoItem("Refresh Approval Status", "Click to poll");
      check.command = { command: "inspectra.refresh", title: "Refresh" };
      check.iconPath = new vscode.ThemeIcon("sync");
      items.push(check);
      return items;
    }

    if (this.status.denied) {
      items.push(new InfoItem("Corpus", "Denied"));
      items.push(new InfoItem("Reason", this.status.reason ?? "Denied by workspace authority"));
      const retry = new InfoItem("Retry Connection", "Click to request again");
      retry.command = { command: "inspectra.corpusRetry", title: "Retry" };
      retry.iconPath = new vscode.ThemeIcon("refresh");
      items.push(retry);
      return items;
    }

    items.push(new InfoItem("Corpus", "Not Connected"));
    const connect = new InfoItem("Connect to Corpus", "Request permission approval");
    connect.command = { command: "inspectra.corpusConnect", title: "Connect" };
    connect.iconPath = new vscode.ThemeIcon("plug");
    items.push(connect);
    return items;
  }
}
