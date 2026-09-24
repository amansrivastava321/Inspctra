# Exportable Run Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate HTML, PDF, JUnit XML, and SARIF exports directly from every terminal Inspectra run and expose honest download controls in the report and run UI.

**Architecture:** A `RunReportExporter` loads one canonical context from `ProductStorage` and `ArtifactIndex`, then pure serializers produce each format without database writes. The reports router enforces terminal eligibility and response headers; one shared React component creates the four safe downloads.

**Tech Stack:** Python 3.11, FastAPI, SQLite, Jinja2, WeasyPrint, Pillow, ElementTree, pytest, React 18, TypeScript, Vitest.

---

### Task 1: Lock the canonical context and text formats

**Files:**
- Create: `tests/test_report_exporters.py`
- Create: `qa_ai/product_backend/report_exporters.py`

- [x] Write a temporary storage/artifact fixture containing one terminal failed run, app, pack, pass/fail/error steps, screenshot, console, API request, and API response evidence.
- [x] Add failing tests for summary counts/duration/provenance, standalone escaped HTML with a base64 screenshot, parseable JUnit counts/elements, and SARIF 2.1.0 rules/results/locations.
- [x] Run `venv/bin/python -m pytest tests/test_report_exporters.py -v` and confirm collection fails because the exporter module is absent.
- [x] Implement `ReportExportError`, canonical context construction, timestamp/duration/status normalization, safe evidence reads, optimized image data URIs, and Jinja auto-escape.
- [x] Implement `export_html`, `export_junit`, `export_sarif`, and `summary` using only the canonical context.
- [x] Run the focused tests and require green results.

### Task 2: Add PDF generation and visual verification

**Files:**
- Modify: `requirements.txt`
- Modify: `tests/test_report_exporters.py`
- Modify: `qa_ai/product_backend/report_exporters.py`

- [x] Add `jinja2>=3.1.0` and `weasyprint>=60.0` to `requirements.txt`.
- [x] Add a failing PDF test requiring `%PDF`, parseable pages/text, a repeating print header definition, step page breaks, and size below 10 MB.
- [x] Run the PDF artifact-operation marker exactly once immediately before the first PDF generation command.
- [x] Implement `export_pdf` by passing the existing HTML to `weasyprint.HTML(...).write_pdf()`; do not create a second template.
- [x] Generate a representative PDF under `tmp/pdfs/`, inspect it with `pdfinfo`/`pypdf`, render every page with `pdftoppm`, and inspect the PNGs for clipping, overlap, broken glyphs, headers, footers, and page transitions.
- [x] Run the focused exporter suite and require green results.

### Task 3: Add run-based API downloads and summary

**Files:**
- Modify: `qa_ai/product_backend/routers/reports.py`
- Modify: `qa_ai/product_backend/models.py`
- Create: `tests/test_report_export_api.py`

- [x] Add failing endpoint tests for all four formats, exact MIME types, `nosniff`, and `Content-Disposition: attachment; filename="inspectra-run-{run_id}.{ext}"`.
- [x] Add failing 404 and pending/running 409 tests with the exact required detail.
- [x] Add a failing summary response test for timestamps, duration, counts, failure reasons, provenance, and ordered formats.
- [x] Define the typed summary response model and add the five routes to the reports router using dependency-injected storage/index.
- [x] Run `venv/bin/python -m pytest tests/test_report_exporters.py tests/test_report_export_api.py -v` and require green results.

### Task 4: Add reusable frontend downloads

**Files:**
- Create: `apps/inspectra_ui/src/components/reports/ReportDownloadButtons.tsx`
- Modify: `apps/inspectra_ui/src/api/client.ts`
- Modify: `apps/inspectra_ui/src/components/reports/ReportSummaryCard.tsx`
- Modify: `apps/inspectra_ui/src/pages/ReportsPage.tsx`
- Modify: `apps/inspectra_ui/src/pages/ReportDetailPage.tsx`
- Modify: `apps/inspectra_ui/src/pages/LiveRunDetailWorkspace.tsx`
- Create: `apps/inspectra_ui/src/test/ReportDownloads.test.tsx`

- [x] Add failing tests that require four labelled buttons, encoded run URLs, meaningful filenames, click isolation inside cards, terminal-run visibility, and disabled demo controls.
- [x] Run the focused Vitest file and confirm failures are caused by the missing component/helper.
- [x] Implement `runReportExportUrl(runId, format)` and the reusable download component using an ephemeral anchor.
- [x] Compose it into report cards, report detail, and terminal run detail without changing routes or existing report generation behavior.
- [x] Run the focused frontend tests and require green results.

### Task 5: Integrated verification

**Files:**
- Modify only files implicated by genuine failures.
- Update: `graphify-out/graph.json`
- Update: `graphify-out/GRAPH_REPORT.md`

- [x] Run `venv/bin/python -m pytest tests/test_report_exporters.py tests/test_report_export_api.py -v`.
- [x] Run `venv/bin/python -m pytest tests/ -v` and record any environment-only exclusions honestly.
- [x] Run `venv/bin/python -m pytest tests/smoke/test_full_journey.py -v`.
- [x] Run `cd apps/inspectra_ui && npm test -- --watchAll=false`.
- [x] Run `cd apps/inspectra_ui && npm run build`.
- [x] Open the generated HTML with network disabled and verify styles, all steps, embedded screenshot, evidence, and provenance.
- [x] Re-render the final PDF and inspect every page; parse JUnit with ElementTree and SARIF with `json.loads` plus structural assertions.
- [x] Refresh Graphify with `venv/bin/python -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`.
- [x] Report changed files, exact test counts, manual artifact verification, build status, and remaining risks without creating a partial root commit.
