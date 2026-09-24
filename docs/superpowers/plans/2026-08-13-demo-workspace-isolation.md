# Demo Workspace Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explicit, deterministic, read-only `/demo` workspace while guaranteeing that real and offline workspaces never receive sample data.

**Architecture:** A route-scoped `WorkspaceModeContext` owns the static demo object and mode-aware navigation. `useApi` selects an explicit demo value without executing its backend callback; real mode remains API-only. Shared routes and pages render both modes so product behavior does not drift.

**Tech Stack:** React 18, React Router 6, TypeScript, Vitest, Testing Library, Playwright, Vite

---

### Task 1: Deterministic demo workspace

**Files:**
- Modify: `apps/inspectra_ui/src/mocks/sampleData.ts`
- Modify: `apps/inspectra_ui/src/types/api.ts`
- Test: `apps/inspectra_ui/src/test/DemoWorkspace.test.ts`

- [ ] **Step 1: Write the failing deterministic-data test**

```ts
it('returns the same complete workspace on every call', () => {
  const first = generateDemoWorkspace();
  const second = generateDemoWorkspace();
  expect(first).toEqual(second);
  expect(first.health).toEqual({ status: 'ok', provenance: 'DEMO_EXAMPLE' });
  expect(first.projects.length).toBeGreaterThan(0);
  expect(first.apps.length).toBeGreaterThan(0);
  expect(first.validationPacks.length).toBeGreaterThan(0);
  expect(first.liveRuns.length).toBeGreaterThan(0);
  expect(first.evidence.length).toBeGreaterThan(0);
  expect(first.reports.length).toBeGreaterThan(0);
});
```

- [ ] **Step 2: Run `npm test -- DemoWorkspace.test.ts --run` and verify it fails because `generateDemoWorkspace` is absent.**
- [ ] **Step 3: Add `Provenance`, `HealthStatus`, and `DemoWorkspace` types, replace dynamic dates and `Math.random()`, and export `generateDemoWorkspace()` returning cloned static records.**
- [ ] **Step 4: Re-run the focused test and verify it passes.**

### Task 2: Explicit route-scoped mode

**Files:**
- Create: `apps/inspectra_ui/src/state/WorkspaceModeContext.tsx`
- Modify: `apps/inspectra_ui/src/App.tsx`
- Modify: `apps/inspectra_ui/src/hooks/useApi.ts`
- Modify: `apps/inspectra_ui/src/api/client.ts`
- Test: `apps/inspectra_ui/src/test/DemoWorkspaceRoute.test.tsx`

- [ ] **Step 1: Write tests asserting `/demo` renders the exact banner, nested demo links retain `/demo`, and backend `get` is never called.**
- [ ] **Step 2: Run the focused test and verify it fails because no demo route/provider exists.**
- [ ] **Step 3: Implement `WorkspaceModeProvider`, `useWorkspaceMode`, `toWorkspacePath`, and a mode-aware `useApi(fn, { demo })`; remove the `VITE_USE_MOCKS` request branch.**
- [ ] **Step 4: Mount the existing route set under real and `/demo/*` boundaries and verify the focused tests pass.**

### Task 3: Persistent shell and honest offline state

**Files:**
- Modify: `apps/inspectra_ui/src/components/layout/AppShell.tsx`
- Modify: `apps/inspectra_ui/src/components/layout/Sidebar.tsx`
- Modify: `apps/inspectra_ui/src/components/common/EmptyState.tsx`
- Test: `apps/inspectra_ui/src/test/DemoWorkspaceRoute.test.tsx`
- Test: `apps/inspectra_ui/src/test/Dashboard.test.tsx`

- [ ] **Step 1: Write tests for the persistent purple banner, Leave Demo, Retry connection, Try Demo, and the absence of demo records while offline.**
- [ ] **Step 2: Run the tests and verify the missing controls and old mock fallback cause failures.**
- [ ] **Step 3: Render `DemoWorkspaceBanner` above every demo page, prefix sidebar links, use static demo projects in the demo sidebar, and extend `OfflineState` with navigation to `/demo`.**
- [ ] **Step 4: Remove page-level mock banners and verify the focused tests pass.**

### Task 4: Shared page data and read-only enforcement

**Files:**
- Modify: `apps/inspectra_ui/src/pages/*.tsx` where `useApi` or mutation controls are used
- Create: `apps/inspectra_ui/src/components/common/DemoReadOnly.tsx`
- Test: `apps/inspectra_ui/src/test/DemoReadOnly.test.tsx`

- [ ] **Step 1: Write tests proving representative create and run controls are disabled and expose the exact approved tooltip.**
- [ ] **Step 2: Run the tests and verify they fail while demo controls remain active.**
- [ ] **Step 3: Replace fallback options with explicit demo selectors for dashboard, projects, packs, runs, evidence, reports, doctor, connectors, models, memory, app details, and pack details.**
- [ ] **Step 4: Add `useDemoReadOnly`/shared tooltip handling, disable all mutation buttons and form controls in demo mode, and guard mutation handlers.**
- [ ] **Step 5: Re-run focused tests and repair any route or type regressions.**

### Task 5: Dashboard health and full verification

**Files:**
- Modify: `apps/inspectra_ui/src/pages/DashboardPage.tsx`
- Test: `apps/inspectra_ui/src/test/Dashboard.test.tsx`
- Test: `apps/inspectra_ui/e2e/demo-workspace.spec.ts`

- [ ] **Step 1: Write a test proving real dashboard health calls `/health`, while demo health remains `DEMO_EXAMPLE` and static.**
- [ ] **Step 2: Implement the health query without synthesizing percentages or merging it with dashboard records.**
- [ ] **Step 3: Run `npm test -- --run`, `npm run build`, and targeted Playwright checks.**
- [ ] **Step 4: Run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` and inspect the final diff for accidental mock imports or enabled demo mutations.**

