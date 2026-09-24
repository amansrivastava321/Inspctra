# CLI UX Guide

Inspectra ships a polished command-line interface built on top of the Python `rich` library for formatted output. All core audit logic is unchanged — the CLI layer is purely presentational.

## Commands

### `inspectra version`
Print version information.

```
$ python -m qa_ai.cli version
Inspectra QA-AI  v1.0.0
```

### `inspectra init [project_dir]`
Scaffold a new project workspace. Creates `artifacts/`, `qa_ai/config/`, and a `.qa_ai` config marker.

```
$ python -m qa_ai.cli init .
✓ Initialised project at /path/to/project
  Created: artifacts/
  Created: qa_ai/config/
```

### `inspectra audit <target> [--profile PROFILE]`
Run a full audit. Output is a Rich summary panel with phase table and severity breakdown.

```
$ python -m qa_ai.cli audit src/ --profile api
╭─────────────────────── Audit Complete ───────────────────────╮
│  Status: COMPLETED   Profile: api   Target: src/             │
│  Phases: discovery  analysis  reporting                      │
│  Findings: 3 (1 critical · 2 high · 0 medium · 0 low)       │
╰──────────────────────────────────────────────────────────────╯
```

### `inspectra doctor`
Run system health checks. Output is a table of checks with Pass/Warn/Fail status.

```
$ python -m qa_ai.cli doctor
 Check        Status   Detail
 ──────────── ──────── ────────────────────────────
 config       ✓ Pass   All required env vars set
 llm          ✓ Pass   Model reachable
 artifact_dir ✓ Pass   artifacts/ exists
```

### `inspectra dashboard <artifacts_dir> [--port PORT] [--host HOST]`
Start the local web dashboard. Opens a FastAPI server at `http://HOST:PORT`.

```
$ python -m qa_ai.cli dashboard artifacts/ --port 8765
Inspectra Dashboard starting…
  URL  : http://127.0.0.1:8765
  Artifacts : /path/to/artifacts/
Press Ctrl+C to stop.
```

## Formatter Module

`qa_ai/cli/formatter.py` — all Rich rendering lives here. Each function accepts a plain dict and renders a formatted output. The module gracefully falls back to plain-text output if `rich` is unavailable.

| Function | Purpose |
|---|---|
| `print_version(version)` | Version banner |
| `print_init_result(result)` | Init scaffold summary |
| `print_audit_summary(result)` | Rich Panel + phases Table |
| `print_doctor_report(result)` | Health checks Table |
| `print_dashboard_starting(host, port, dir)` | Dashboard start notice |
| `print_result(result, command)` | Generic fallback |

## Environment Variables

See `qa_ai/config/settings.py` for the full list. Relevant to CLI:

| Variable | Default | Effect |
|---|---|---|
| `QA_AI_PROFILE` | `default` | Default audit profile |
| `QA_AI_OUTPUT_DIR` | `artifacts` | Where artifacts are written |
| `QA_AI_LOG_LEVEL` | `INFO` | Logging verbosity |
