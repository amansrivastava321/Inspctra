# Inspectra QA — VS Code Extension

View Inspectra QA-AI audit results directly in VS Code.

## Features

- **Findings sidebar** — all audit findings with severity icons, click to open a detail panel
- **Risk & Summary sidebar** — risk score, risk level, audit status, profile, and phases
- **Refresh command** — pull latest data from the running local dashboard
- **Open Dashboard** — open the full HTML dashboard in your browser

## Requirements

The Inspectra local dashboard must be running:

```bash
python -m qa_ai.cli dashboard artifacts/ --port 8765
```

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `inspectra.dashboardUrl` | `http://127.0.0.1:8765` | URL of the running Inspectra dashboard |
| `inspectra.artifactsDir` | `artifacts` | Fallback: relative path to artifacts |

## Commands

| Command | Description |
|---------|-------------|
| `Inspectra: Refresh` | Reload findings and risk data |
| `Inspectra: Open Dashboard` | Open the full dashboard in a browser |

## Development

```bash
cd vscode-extension
npm install
npm run compile   # or: npm run watch
# Press F5 in VS Code to launch Extension Development Host
```

## Architecture

```
extension.ts          activation, provider registration
├── treeProviders.ts  FindingsProvider, RiskProvider (VS Code TreeDataProvider)
├── commands.ts       refresh, openDashboard, showFindingDetail
└── apiClient.ts      HTTP GET helpers for /api/* routes
```

All data flows from the Inspectra dashboard API — the extension never touches
the filesystem directly.
