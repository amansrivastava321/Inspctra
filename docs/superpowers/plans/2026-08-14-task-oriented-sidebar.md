# Task-Oriented Sidebar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Inspectra's flat sidebar with persistent task-oriented navigation groups and an accessible shell visibility toggle.

**Architecture:** A typed navigation configuration in `Sidebar.tsx` owns labels, paths, icons, active matching, and group defaults. `AppShell` owns visibility, `Topbar` renders the toggle, and `LiveRunsPage` interprets the manual-view query. Existing paths remain valid, with one additive Runtime Doctor alias.

**Tech Stack:** React 19, TypeScript, React Router, Lucide React, Vitest, Testing Library, localStorage.

---

### Task 1: Lock sidebar behavior with tests

**Files:**
- Modify: `apps/inspectra_ui/src/test/Sidebar.test.tsx`
- Create: `apps/inspectra_ui/src/test/AppShellSidebar.test.tsx`

- [ ] Add tests for four group headers, new-user defaults, header toggling, localStorage persistence, active-route expansion, duplicate-route matching, Preview integrations, quick-action navigation, demo-disabled actions, and the shell hamburger.
- [ ] Run `npm test -- --run src/test/Sidebar.test.tsx src/test/AppShellSidebar.test.tsx` from `apps/inspectra_ui` and confirm failures are caused by the missing grouped navigation.

### Task 2: Implement grouped navigation

**Files:**
- Modify: `apps/inspectra_ui/src/components/layout/Sidebar.tsx`

- [ ] Replace the flat array with typed `NAV_GROUPS` configuration and exact active matchers.
- [ ] Add accessible collapsible headers and versioned localStorage persistence.
- [ ] Add Quick Actions, Preview labeling, logo-to-dashboard navigation, and demo guards.
- [ ] Re-run focused sidebar tests and confirm they pass.

### Task 3: Add shell visibility and route compatibility

**Files:**
- Modify: `apps/inspectra_ui/src/components/layout/AppShell.tsx`
- Modify: `apps/inspectra_ui/src/components/layout/Topbar.tsx`
- Modify: `apps/inspectra_ui/src/App.tsx`
- Modify: `apps/inspectra_ui/src/pages/LiveRunsPage.tsx`

- [ ] Add a shell-owned sidebar visibility state and accessible Topbar hamburger.
- [ ] Preserve `/doctor` and add `/runtime-doctor` for the approved navigation mapping.
- [ ] Make `?mode=manual` filter and label the existing runs page.
- [ ] Run the focused tests and TypeScript build.

### Task 4: Verify the integrated result

**Files:**
- Modify only if a regression is exposed.

- [ ] Run `npm test -- --watchAll=false` from `apps/inspectra_ui`.
- [ ] Run `npm run build` from the repository root.
- [ ] Verify grouping, persistence, active states, quick actions, demo locks, and hamburger behavior in the browser.
- [ ] Refresh Graphify with `venv/bin/python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`.

