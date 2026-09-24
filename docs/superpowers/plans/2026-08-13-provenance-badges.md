# Provenance Badges Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render an honest, consistent provenance badge on every requested backend-backed UI surface.

**Architecture:** A single typed badge owns normalization, labels, colors, tooltips, and development warnings. Pages explicitly pass the provenance of the closest displayed artifact or response, preserving demo isolation and avoiding badges on UI chrome.

**Tech Stack:** React, TypeScript, existing Inspectra design tokens and inline styles, Vitest/Testing Library, Playwright.

---

### Task 1: Badge contract

**Files:**
- Create: `apps/inspectra_ui/src/components/ProvenanceBadge.tsx`
- Create: `apps/inspectra_ui/src/test/ProvenanceBadge.test.tsx`

- [ ] Write tests for all six mappings, tooltips, inline styling, missing fallback, and warning.
- [ ] Run the test and confirm it fails because the component is absent.
- [ ] Implement the minimal reusable badge.
- [ ] Run the focused test and confirm it passes.

### Task 2: Collection surfaces

**Files:**
- Modify: `DashboardPage.tsx`, `ProjectsPage.tsx`, `ValidationPacksPage.tsx`, `LiveRunsPage.tsx`, `EvidenceCenterPage.tsx`, `ReportsPage.tsx`
- Modify: `DemoWorkspaceRoute.test.tsx` and relevant page tests

- [ ] Add failing assertions for badges on every repeated card/row and dashboard metric.
- [ ] Add badges using the closest response/item provenance.
- [ ] Verify focused collection tests.

### Task 3: Detail surfaces

**Files:**
- Modify: `AppDetailPage.tsx`, `PackDetailPage.tsx`, `LiveRunDetailPage.tsx`, `ReportDetailPage.tsx`, `EvidenceCenterPage.tsx`
- Modify relevant detail tests and `e2e/demo-workspace.spec.ts`

- [ ] Add failing assertions for detail headers and nested result/evidence rows.
- [ ] Add detail badges with explicit source labels.
- [ ] Verify focused detail and browser tests.

### Task 4: Full verification

- [ ] Run all frontend tests.
- [ ] Run the production build.
- [ ] Verify backend-online health and representative API provenance without mutating user data.
- [ ] Verify demo and offline browser behavior.
- [ ] Request independent review and address Critical/Important findings.
- [ ] Refresh Graphify.

