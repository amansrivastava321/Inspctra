/**
 * extension.ts - Entry point for the Inspectra QA VS Code extension.
 *
 * Registers tree providers, commands, and an initial data fetch on activation.
 */
import * as vscode from "vscode";
import { FindingsProvider, RiskProvider, CorpusProvider } from "./treeProviders";
import { registerCommands } from "./commands";
import { checkHealth } from "./apiClient";

export function activate(context: vscode.ExtensionContext): void {
  const findingsProvider = new FindingsProvider();
  const riskProvider = new RiskProvider();
  const corpusProvider = new CorpusProvider();

  context.subscriptions.push(
    vscode.window.registerTreeDataProvider("inspectra.findings", findingsProvider),
    vscode.window.registerTreeDataProvider("inspectra.risk", riskProvider),
    vscode.window.registerTreeDataProvider("inspectra.corpus", corpusProvider)
  );

  registerCommands(context, findingsProvider, riskProvider, corpusProvider);

  // Initial load — silently skip if the dashboard is not running yet.
  void _initialLoad(findingsProvider, riskProvider, corpusProvider);
}

async function _initialLoad(
  findingsProvider: FindingsProvider,
  riskProvider: RiskProvider,
  corpusProvider: CorpusProvider
): Promise<void> {
  const up = await checkHealth();
  if (!up) {
    return; // Dashboard not running; user will trigger refresh manually.
  }
  await Promise.all([findingsProvider.refresh(), riskProvider.refresh(), corpusProvider.refresh()]);
}

export function deactivate(): void {}
