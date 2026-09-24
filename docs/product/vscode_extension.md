# VS Code Extension

The Inspectra VS Code extension (`vscode-extension/`) surfaces audit findings and risk data in a sidebar without leaving your editor.

## Prerequisites

The Inspectra local dashboard must be running (the extension reads from its API):

```bash
python -m qa_ai.cli dashboard artifacts/ --port 8765
```

## Installation (Development)

```bash
cd vscode-extension
npm install
npm run compile
# Press F5 in VS Code → Extension Development Host opens
```

## Views

### Findings (`inspectra.findings`)
Lists every audit finding with severity icons:
- `$(error)` critical
- `$(warning)` high
- `$(info)` medium
- `$(pass)` low

Click a finding to open a detail panel with description, tags, and evidence.

### Risk & Summary (`inspectra.risk`)
Displays: Status, Risk Level, Risk Score, Profile, Target, Phases Executed.

## Commands

| Command | Keybinding | Description |
|---|---|---|
| `Inspectra: Refresh` | (toolbar button) | Reload all data from the dashboard |
| `Inspectra: Open Dashboard` | — | Open full HTML dashboard in browser |

## Configuration

Open **Settings → Extensions → Inspectra QA**:

| Setting | Default | Description |
|---|---|---|
| `inspectra.dashboardUrl` | `http://127.0.0.1:8765` | Dashboard URL |
| `inspectra.artifactsDir` | `artifacts` | Fallback artifacts path |

## File Layout

```
vscode-extension/
├── package.json          VS Code extension manifest + npm scripts
├── tsconfig.json         TypeScript compiler config
├── README.md
└── src/
    ├── extension.ts      Activation entry point
    ├── apiClient.ts      HTTP GET wrappers for /api/* routes
    ├── treeProviders.ts  FindingsProvider, RiskProvider (TreeDataProvider)
    └── commands.ts       refresh, openDashboard, showFindingDetail handlers
```

## Data Flow

```
extension.ts (activate)
  ├── registers FindingsProvider → /api/findings
  ├── registers RiskProvider    → /api/risk + /api/summary
  └── registers commands
        └── refresh → re-fetches all providers
              showFindingDetail → opens WebviewPanel with finding HTML
```

All HTTP calls go through `apiClient.ts` which reads the `inspectra.dashboardUrl` setting on every call, so port changes take effect immediately without restarting the extension.
