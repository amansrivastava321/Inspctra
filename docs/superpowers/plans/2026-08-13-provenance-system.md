# Provenance System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and expose a stable source-of-truth label for Inspectra entities, execution artifacts, and health responses.

**Architecture:** Define one string enum in the backend models, persist it through additive SQLite columns, label every execution step at its source, and aggregate step labels into the durable run label. Response models enforce the public contract while route code sets provenance for live/non-persisted health data.

**Tech Stack:** Python, FastAPI, Pydantic, SQLite, pytest

---

### Task 1: Lock the public provenance contract

**Files:**
- Create: `tests/test_product_backend_provenance.py`
- Modify: `qa_ai/product_backend/models.py`

- [ ] Write failing tests asserting enum values and provenance serialization on project, app, pack, run, evidence, report, dashboard, and health responses.
- [ ] Run `python -m pytest tests/test_product_backend_provenance.py -v` and confirm failures are caused by the missing enum/fields.
- [ ] Add `Provenance(str, Enum)` and `Field(default=Provenance.UNAVAILABLE)` fields without removing existing model fields.
- [ ] Add a typed health response and run the focused tests to green.

### Task 2: Persist provenance and migrate existing databases

**Files:**
- Modify: `qa_ai/product_backend/storage.py`
- Test: `tests/test_product_backend_provenance.py`

- [ ] Write failing storage tests for new rows, persisted reads, and legacy run fallback.
- [ ] Add provenance columns to fresh schema definitions and independent additive `ALTER TABLE` migration statements for existing databases.
- [ ] Store and deserialize provenance for projects, app targets, validation packs, runs, evidence, and reports.
- [ ] Normalize invalid/missing values to `UNAVAILABLE`; classify a legacy run with evidence as `REAL_EXECUTION`.
- [ ] Run focused storage tests to green.

### Task 3: Label and aggregate executions

**Files:**
- Modify: `qa_ai/product_backend/run_manager.py`
- Modify: `qa_ai/product_backend/routers/validation_packs.py`
- Modify: `qa_ai/product_backend/routers/live_runs.py`
- Test: `tests/test_product_backend_provenance.py`

- [ ] Write failing tests for real, dry-run, unavailable, uniform, and mixed step aggregation.
- [ ] Label HTTP/Playwright results `REAL_EXECUTION`, structural fallbacks `DRY_RUN`, and capability gaps `UNAVAILABLE`.
- [ ] Persist step provenance and recompute run provenance after each step and finalization.
- [ ] Set new runs to `UNAVAILABLE`, preserve provenance during retests, and make reports inherit the stored run provenance.
- [ ] Run focused execution tests to green.

### Task 4: Expose provenance through all required APIs

**Files:**
- Modify: `qa_ai/product_backend/routers/projects.py`
- Modify: `qa_ai/product_backend/routers/apps.py`
- Modify: `qa_ai/product_backend/routers/validation_packs.py`
- Modify: `qa_ai/product_backend/routers/dashboard.py`
- Modify: `qa_ai/product_backend/routers/models.py`
- Modify: `qa_ai/product_backend/server.py`
- Modify: `tests/smoke/test_full_journey.py`
- Test: `tests/test_product_backend_provenance.py`

- [ ] Write failing API tests for entity list/detail routes, health, model health, dashboard, evidence, and reports.
- [ ] Set user-created persistent entities and live workspace data to `REAL_EXECUTION`.
- [ ] Return `UNAVAILABLE` from failed health probes.
- [ ] Assert provenance in the smoke run response.
- [ ] Run focused API tests and the smoke test to green.

### Task 5: End-to-end verification

**Files:**
- Verify all modified files.

- [ ] Run `python -m pytest tests/test_product_backend_provenance.py tests/test_product_backend_storage.py tests/test_product_backend_api.py -v`.
- [ ] Run `python -m pytest tests/smoke/test_full_journey.py -v` with network/browser access.
- [ ] Start `npm run start:backend`, curl `/api/health` and an available run endpoint, then stop the server.
- [ ] Run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` and report if the optional local package is unavailable.
