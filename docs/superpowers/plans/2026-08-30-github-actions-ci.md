# GitHub Actions CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic, least-privilege GitHub Actions validation for the Python backend and active React frontend.

**Architecture:** A single workflow contains independent backend and frontend jobs. Committed dependency manifests and lockfiles provide all tools; a backend contract test guards workflow structure, while a Vitest component test guards the root error boundary.

**Tech Stack:** GitHub Actions, YAML/PyYAML, Python 3.11/pytest, Node 18/npm workspaces, ESLint 8, TypeScript ESLint 6, React 18/Vitest.

---

### Task 1: Add the failing workflow contract

**Files:**
- Create: `tests/ci/test_ci_workflow.py`
- Create later: `.github/workflows/ci.yml`

- [x] Write a pytest contract that loads the workflow with `yaml.BaseLoader`, asserts push and pull-request triggers, `contents: read`, independent jobs, timeouts, pinned setup actions, exact runtimes, and required backend/frontend commands.
- [x] Assert that frontend commands contain `npm ci` and do not contain runtime `npm install`, lint suppression, `continue-on-error`, or deployment steps.
- [x] Run `venv/bin/python -m pytest tests/ci/test_ci_workflow.py -v` and confirm it fails because `.github/workflows/ci.yml` is absent.

### Task 2: Add deterministic lint tooling

**Files:**
- Modify: `apps/inspectra_ui/package.json`
- Modify: `package-lock.json`
- Modify: `apps/inspectra_ui/package-lock.json`
- Create: `apps/inspectra_ui/.eslintrc.cjs`

- [x] Add `eslint`, `@typescript-eslint/parser`, and `@typescript-eslint/eslint-plugin` to frontend `devDependencies`.
- [x] Add the TypeScript-aware ESLint configuration with explicit-any and unused-variable warnings and a read-only Vitest global.
- [x] Regenerate committed lockfiles without installing tools dynamically in CI.
- [x] Run `npm run lint --workspace=inspectra-ui`, address configuration defects only, and require exit code 0.

### Task 3: Add the failing error-boundary tests

**Files:**
- Create: `apps/inspectra_ui/src/test/ErrorBoundary.test.tsx`
- Create later: `apps/inspectra_ui/src/components/ErrorBoundary.tsx`
- Modify later: `apps/inspectra_ui/src/App.tsx`

- [x] Write one test that renders a throwing child and expects the default recovery UI.
- [x] Write one test that expects a supplied custom fallback.
- [x] Run `npm test --workspace=inspectra-ui -- --watchAll=false src/test/ErrorBoundary.test.tsx` and confirm failure because the component is absent.
- [x] Implement the minimal class boundary and wrap `BrowserRouter` with it in `App.tsx`.
- [x] Re-run the focused test and require both tests to pass.

### Task 4: Implement the workflow and documentation

**Files:**
- Create: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `.gitignore`

- [x] Add every-push/every-pull-request triggers, `contents: read`, and parallel `backend`/`frontend` jobs with bounded timeouts.
- [x] Add the Python 3.11 compile, collection, smoke, and backend-suite steps, excluding only `tests/smoke/test_external_real_execution.py` from the broad suite.
- [x] Add the Node 18 frozen workspace install, lint, test, and build steps using the root lockfile cache key.
- [x] Add the approved placeholder CI badge to the README.
- [x] Add explicit `data/*.db` and blanket `artifacts/` ignore coverage while preserving the existing secrets, dependency, cache, and build rules.
- [x] Run the workflow contract and require it to pass.

### Task 5: Simulate CI locally

**Files:**
- No new production files.

- [x] Validate YAML with available local tooling and run `venv/bin/python -m pytest tests/ci/test_ci_workflow.py -v`.
- [x] Run `venv/bin/python -m compileall qa_ai/`.
- [x] Run `venv/bin/python -m pytest --collect-only` and record the collected count.
- [x] Run `venv/bin/python -m pytest tests/smoke/test_full_journey.py -v`.
- [x] Run `venv/bin/python -m pytest tests/ -v --ignore=tests/smoke/test_external_real_execution.py` and record pass/skip/failure counts.
- [x] Run a frozen frontend install using the same root workspace lockfile as CI.
- [x] Run `npm run lint --workspace=inspectra-ui`.
- [x] Run `npm test --workspace=inspectra-ui -- --watchAll=false` and record counts.
- [x] Run `npm run build --workspace=inspectra-ui`.
- [x] Rebuild Graphify with the repository-required `_rebuild_code(Path('.'))` command.
- [x] Review the complete diff, re-check the approved specification, and report files, test counts, warnings, and remaining risks.
