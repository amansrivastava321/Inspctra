/**
 * commands.ts - VS Code command handlers for the Inspectra extension.
 */
import * as vscode from "vscode";
import { Finding, requestCorpusConnection, disconnectCorpus } from "./apiClient";
import { FindingsProvider, RiskProvider, CorpusProvider } from "./treeProviders";

export function registerCommands(
  context: vscode.ExtensionContext,
  findingsProvider: FindingsProvider,
  riskProvider: RiskProvider,
  corpusProvider: CorpusProvider
): void {
  context.subscriptions.push(
    vscode.commands.registerCommand("inspectra.refresh", async () => {
      await Promise.all([findingsProvider.refresh(), riskProvider.refresh(), corpusProvider.refresh()]);
    }),

    vscode.commands.registerCommand("inspectra.openDashboard", () => {
      const cfg = vscode.workspace.getConfiguration("inspectra");
      const url = cfg.get<string>("dashboardUrl") ?? "http://127.0.0.1:8765";
      void vscode.env.openExternal(vscode.Uri.parse(url));
    }),

    vscode.commands.registerCommand("inspectra.corpusConnect", async () => {
      const ok = await requestCorpusConnection();
      if (!ok) {
        vscode.window.showErrorMessage("Could not request Corpus connection.");
      }
      await corpusProvider.refresh();
    }),

    vscode.commands.registerCommand("inspectra.corpusRetry", async () => {
      const ok = await requestCorpusConnection();
      if (!ok) {
        vscode.window.showErrorMessage("Could not retry Corpus connection.");
      }
      await corpusProvider.refresh();
    }),

    vscode.commands.registerCommand("inspectra.corpusDisconnect", async () => {
      const ok = await disconnectCorpus();
      if (!ok) {
        vscode.window.showErrorMessage("Could not disconnect Corpus session.");
      }
      await corpusProvider.refresh();
    }),

    vscode.commands.registerCommand(
      "inspectra.showFindingDetail",
      (finding: Finding) => {
        const panel = vscode.window.createWebviewPanel(
          "inspectraFinding",
          `Finding: ${finding.title ?? finding.id ?? "Detail"}`,
          vscode.ViewColumn.Beside,
          {}
        );
        panel.webview.html = buildFindingHtml(finding);
      }
    )
  );
}

function buildFindingHtml(f: Finding): string {
  const esc = (s: string) =>
    s
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;");

  const sev = (f.severity ?? "unknown").toLowerCase();
  const sevColor: Record<string, string> = {
    critical: "#fca5a5",
    high: "#fed7aa",
    medium: "#fef08a",
    low: "#86efac",
  };
  const color = sevColor[sev] ?? "#94a3b8";
  const tags = (f.tags ?? []).map((t) => `<span class="tag">${esc(t)}</span>`).join(" ");
  const evidence = f.evidence
    ? `<pre>${esc(JSON.stringify(f.evidence, null, 2))}</pre>`
    : "<em style='color:#64748b'>None</em>";

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
  body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;padding:1.5rem;font-size:14px}
  h1{font-size:1.1rem;font-weight:700;margin-bottom:.5rem}
  .meta{color:#64748b;font-size:.8rem;margin-bottom:1rem}
  .sev{font-weight:700;color:${color}}
  section{margin-top:1rem}
  h2{font-size:.8rem;text-transform:uppercase;letter-spacing:.05em;color:#94a3b8;margin-bottom:.4rem}
  p{line-height:1.6}
  pre{background:#1e293b;padding:1rem;border-radius:6px;overflow:auto;font-size:.8rem;color:#a5f3fc}
  .tag{background:#1e293b;border:1px solid #334155;border-radius:3px;padding:.1rem .4rem;
       font-size:.75rem;color:#94a3b8;margin:.1rem}
</style>
</head>
<body>
<h1>${esc(f.title ?? f.id ?? "Finding")}</h1>
<p class="meta">
  ID: ${esc(f.id ?? "—")} &nbsp;|&nbsp;
  Severity: <span class="sev">${esc((f.severity ?? "?").toUpperCase())}</span> &nbsp;|&nbsp;
  Category: ${esc(f.category ?? "—")}
</p>
${tags ? `<p>${tags}</p>` : ""}
${f.description ? `<section><h2>Description</h2><p>${esc(f.description)}</p></section>` : ""}
<section><h2>Evidence</h2>${evidence}</section>
</body>
</html>`;
}
