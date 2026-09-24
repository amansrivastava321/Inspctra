# Archive Obsolete Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the obsolete root React frontend under a clearly deprecated archive while proving the active UI and backend remain operable.

**Architecture:** Move the untracked `frontend/` tree intact to `archive/frontend-deprecated/`; do not rewrite either frontend. Update repository documentation, then validate root configuration references, record maintainability line counts, and exercise the active build/start/test paths.

**Tech Stack:** Shell filesystem operations, Markdown, npm/Vite/TypeScript, FastAPI/Uvicorn, pytest.

---

### Task 1: Archive the obsolete frontend

**Files:**
- Move: `frontend/` → `archive/frontend-deprecated/`
- Create: `archive/frontend-deprecated/README.md`
- Modify: `README.md`

- [x] Confirm `frontend/` exists and `archive/frontend-deprecated/` does not.
- [x] Because `git rev-parse --verify HEAD` fails and the tree is untracked, run `mkdir -p archive` followed by `mv frontend archive/frontend-deprecated`.
- [x] Create the deprecation README with the requested status, archive date, and replacement path.
- [x] Add an “Active frontend” section to the root README stating that `apps/inspectra_ui/` is active and `archive/frontend-deprecated/` is archived.
- [x] Verify the source path is absent and the archive path plus label are present.

### Task 2: Verify references and maintainability boundaries

**Files:**
- Inspect: `package.json`
- Inspect: `tsconfig.json` when present
- Inspect: `.github/` when present
- Inspect: `apps/inspectra_ui/src/pages/**/*.tsx`
- Inspect: `qa_ai/product_backend/**/*.py`

- [x] Search active build/config files for the literal root path `frontend/`, excluding the archive and documentation that intentionally describe it.
- [x] Confirm the root npm workspace contains only `apps/inspectra_ui` and record that no root `tsconfig.json` exists.
- [x] Run `find apps/inspectra_ui/src/pages -name "*.tsx" -exec wc -l {} +` and save all page counts.
- [x] Run `find qa_ai/product_backend -name "*.py" -exec wc -l {} +` and save all backend counts.
- [x] Flag every active source file above 600 lines without changing application code.

### Task 3: Verify active runtime paths

**Files:**
- No application-code changes expected.

- [x] Run `cd apps/inspectra_ui && npm run build`; require exit code 0.
- [x] Run `npm run start:backend`, wait for Uvicorn startup, request `http://127.0.0.1:8765/api/health`, then stop the process cleanly.
- [x] Run `cd apps/inspectra_ui && npm test -- --watchAll=false`; require all frontend tests to pass.
- [x] Run `venv/bin/python -m pytest tests/smoke/test_full_journey.py -v`; require the full journey to pass with external network permission.
- [x] Rebuild Graphify with `venv/bin/python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`.
- [x] Report the move, documentation, searches, complete line counts, files above 600 lines, verification outputs, and any remaining risk.
