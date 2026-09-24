# GitHub Actions CI Design

**Date:** 2026-08-30

## Goal

Add reproducible GitHub Actions continuous integration that independently validates the Python backend and active React frontend on every push and pull request.

## Current state

- The repository has no workflow under `.github/workflows/`.
- The active frontend has a `lint` script, but ESLint and its TypeScript parser/plugin are absent from both dependency manifests and lockfiles.
- `src/components/ErrorBoundary.tsx` is absent and `App.tsx` has no root error boundary.
- The Vitest setup already supplies a working in-memory `localStorage`; no localStorage change is needed.
- The root `.gitignore` already covers most generated files, but it does not use the requested blanket `artifacts/` rule or explicit `data/*.db` rule.
- No Git remote is configured, so the README badge must retain the approved `OWNER/REPO` placeholder.

## Workflow architecture

Create one workflow with independent `backend` and `frontend` jobs. Both jobs use `ubuntu-latest`, have explicit timeouts, and inherit only `contents: read`. The workflow runs for every push and every pull request.

The backend job checks out the repository, installs Python 3.11 with pip caching keyed by `requirements.txt`, installs the committed requirements, compiles `qa_ai/`, collects the suite, runs the product smoke journey, and runs all repository tests except the explicitly opt-in external real-execution smoke test.

The frontend job checks out the repository, installs Node 18 with npm caching keyed by the root workspace lockfile, performs a frozen workspace install with `npm ci`, then runs lint, unit tests, and the production build. ESLint is never installed dynamically in CI and lint failures are never suppressed.

## Deterministic frontend tooling

Add ESLint 8 and the TypeScript ESLint 6 parser/plugin to `apps/inspectra_ui/package.json`, then regenerate the authoritative root workspace lockfile. Add a CommonJS ESLint configuration covering browser, Node, TypeScript, JSX, and Vitest's `vi` global. Explicit `any` and unused variables remain warnings as required; actual parser or recommended-rule errors fail CI.

## Error isolation

Add a class-based `ErrorBoundary` with a default recovery screen and optional custom fallback. Wrap the router at the `App` root so render failures below it do not blank the entire desktop/web shell. Component tests cover both default and custom fallbacks.

## Workflow contract

Add a Python contract test that parses `.github/workflows/ci.yml` as YAML and verifies:

- push and pull-request triggers;
- read-only repository permissions;
- independent backend/frontend jobs with bounded timeouts;
- Python 3.11 and Node 18 setup;
- pinned major action references;
- required compile, collect, smoke, full-test, lint, test, and build commands;
- frozen npm installation and absence of runtime ESLint installation or lint suppression.

This test is part of the backend suite, so accidental weakening of CI fails CI itself.

## Security and failure behavior

The workflow does not use `pull_request_target`, secrets, write permissions, deployment steps, or AI-agent actions. Each command fails normally: no `continue-on-error`, no `|| true`, and no lint-skip fallback. The external network/browser smoke remains excluded from the broad backend suite because it is explicitly opt-in; the required product smoke test still runs separately.

## Documentation and repository hygiene

Add the approved placeholder CI badge below the README title. Ensure root ignore rules cover dependency directories, Python bytecode, environment files, SQLite data, generated evidence, and build output. Do not add deployment behavior.

## Verification

Verification mirrors the workflow locally: YAML/contract validation, Python compilation and collection, focused smoke and backend suite, clean npm install, lint, frontend unit tests, and production build. The focused error-boundary test is run separately to make its result explicit.

