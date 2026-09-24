# Demo Workspace Isolation Design

## Goal

Keep Inspectra's sample workspace completely separate from the user's backend-backed workspace. Demo data must be deterministic, explicit, visually distinct, and incapable of triggering writes or executions.

## Approved behavior

- Real mode uses backend responses only. A failed request produces an honest offline or error state and never substitutes sample data.
- Demo mode is entered explicitly at `/demo` and remains active across demo-prefixed navigation such as `/demo/projects` and `/demo/runs/run-001`.
- `generateDemoWorkspace()` returns a new, complete, deterministic workspace object containing projects, apps, validation packs, runs, evidence, reports, dashboard metrics, health, and supporting page data.
- Every demo artifact uses fixed identifiers, timestamps, metrics, and `DEMO_EXAMPLE` provenance. No date or random-number generation occurs.
- Demo mode is read-only. Create, edit, delete, generate, retry-run, and run controls are disabled with the tooltip: “Available in your real workspace. Leave demo to get started.” Form controls are disabled or read-only.
- The only active demo CTA that changes workspace mode is “Leave Demo.” It returns to the equivalent real route when possible.
- Every demo page has a persistent purple banner reading: “Demo Workspace — Sample data for exploration. No real tests are running.”
- Offline pages retain navigation and show “Backend offline,” “Retry connection,” and “Try Demo,” without metrics or sample records.
- Real dashboard health is fetched from `/api/health`; demo dashboard health is provided by the static workspace.

## Architecture

`WorkspaceModeContext` derives `mode: 'real' | 'demo'` from the route boundary and owns one memoized call to `generateDemoWorkspace()`. The application uses one shared route definition twice: at the existing real paths and beneath `/demo/*`. Navigation helpers prefix internal links in demo mode so the banner and data source persist.

`useApi` becomes mode-aware. In real mode it invokes the supplied backend function and preserves existing loading/offline/error behavior. In demo mode it resolves only the explicitly supplied selector from the static demo workspace and never invokes the backend function. The environment-based `VITE_USE_MOCKS` branch is removed so demo data cannot be activated implicitly.

Shared shell components render either the demo banner or backend-status banner. `OfflineState` exposes retry and demo-entry actions. Demo-safe button and form helpers enforce the read-only contract consistently; individual mutation handlers also guard against demo mode so a disabled-control regression cannot send a request.

## Data flow

```text
real route -> WorkspaceMode(real) -> useApi -> /api -> backend response or offline state
demo route -> WorkspaceMode(demo) -> demo selector -> generateDemoWorkspace() -> static UI
```

There is no merge step between these flows.

## Verification

- Unit tests prove two generated workspaces are deeply equal and contain no randomized/current timestamps.
- Component tests prove real offline mode displays no demo metrics and offers Retry/Try Demo.
- Routing tests prove `/demo` and nested demo navigation retain the banner and make no API calls.
- Demo interaction tests prove mutation controls are disabled with the approved tooltip.
- TypeScript build, Vitest suite, and targeted Playwright browser checks verify the integrated behavior.

