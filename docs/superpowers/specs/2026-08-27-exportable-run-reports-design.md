# Exportable Run Reports Design

**Date:** 2026-08-27

## Goal

Give every terminal Inspectra run shareable HTML, PDF, JUnit XML, and SARIF 2.1.0 exports without requiring a previously generated or persisted report record. Exports are generated from persisted run, pack, app, step, evidence, and provenance data at request time.

## Architecture

Create `qa_ai/product_backend/report_exporters.py` with a `RunReportExporter` that owns one canonical loading path and four pure serialization methods. The constructor receives `ProductStorage` and `ArtifactIndex`; `build_context(run_id)` loads and normalizes the run, app, pack, steps, and evidence once. `export_html`, `export_pdf`, `export_junit`, `export_sarif`, and `summary` all consume that same context so counts, durations, errors, evidence, and provenance cannot drift between formats.

No generated export is written to SQLite or the artifacts directory. The existing persisted JSON `ReportRecord` flow remains compatible, but it is not a prerequisite for the new run-based endpoints. The optional five-minute cache is intentionally omitted for the MVP because generation is local, evidence may change after manual confirmation, and correctness is more valuable than process-local cache complexity.

## Eligibility and errors

Only runs with status `completed`, `failed`, or `cancelled` are exportable. A missing run returns 404. A pending or running run returns HTTP 409 with the exact detail `Report not available — run is still in progress.` Unknown non-terminal statuses use the same 409 response rather than guessing that the run is complete.

Evidence files are read only through `ArtifactIndex.stream_file`, retaining its resolved-path containment checks. Missing or unreadable evidence never prevents the textual report from being generated; the report labels that artifact unavailable. Jinja auto-escaping is enabled and evidence text is rendered as escaped text, never trusted markup.

## Canonical report context

The internal context contains:

- run ID, status, execution mode, provenance, start/end timestamps, and duration;
- app ID, name, base URL, and pack ID/name;
- normalized steps with stable index/ID, display name, action type, status, duration, expected value, actual value, error/failure reason, provenance, and related evidence;
- screenshot data URIs built from safe persisted artifacts;
- console and API request/response evidence as formatted escaped text;
- total, passed, failed, and error counts plus unique failure reasons;
- one generation timestamp shared by the selected export.

Step status `error` contributes to `steps_error`; `failed`, `fail`, `blocked`, and `inconclusive` contribute to `steps_failed`; `passed` and `pass` contribute to `steps_passed`. Other statuses remain visible but do not become failures or errors. Duration uses explicit step duration fields when present and otherwise remains unavailable. Run duration uses completed minus started when both timestamps parse successfully.

## HTML

The HTML export is a complete document with embedded CSS and assets. It defaults to a dark palette and supports light mode with `prefers-color-scheme`. The summary includes app, pack, status, provenance, timestamps, duration, and counts. Each step shows status, duration, expected/actual values, error details, provenance, embedded screenshots, and collapsible console/API evidence. A generated-at footer identifies Inspectra.

Images are decoded through Pillow, bounded to 1600 pixels on the longest edge, and encoded as optimized JPEG or PNG data URIs. If image optimization fails, the original safe bytes are embedded only when the MIME type is an allowed raster image type. SVG is not embedded as active image content.

## PDF

WeasyPrint converts the same self-contained HTML to PDF. Print CSS adds A4 margins, a repeating run/status header, page counters, print-safe colors, and page breaks between step sections. The exporter does not duplicate report markup. Optimized images keep a typical ten-step report below 10 MB; tests use representative evidence and assert the generated PDF is parseable and within the limit.

## JUnit XML

Python's `xml.etree.ElementTree` builds one `testsuite` and one `testcase` per step. The suite includes name, timestamp, duration, tests, failures, and errors. Failed steps receive `failure`; error steps receive `error`; console evidence is combined into `system-out`. ElementTree supplies correct XML escaping and the result includes an XML declaration.

## SARIF

The SARIF exporter emits version 2.1.0 with the OASIS schema URL and `Inspectra` driver. Failed/error steps create results with a stable sanitized rule ID derived from action type or step name, exact failure text, and `error` level. Warning-like step statuses create `warning` results. When an app URL is available, the result contains an artifact location URI. Driver rules are deduplicated and contain human-readable names.

## HTTP API

`qa_ai/product_backend/routers/reports.py` adds:

- `GET /api/runs/{run_id}/report?format=html`
- `GET /api/runs/{run_id}/report?format=pdf`
- `GET /api/runs/{run_id}/report?format=junit`
- `GET /api/runs/{run_id}/report?format=sarif`
- `GET /api/runs/{run_id}/report/summary`

The format query is required and restricted to the four supported values. Responses use `text/html; charset=utf-8`, `application/pdf`, `application/xml; charset=utf-8`, and `application/json` respectively. Every download returns `Content-Disposition: attachment; filename="inspectra-run-{safe_run_id}.{ext}"` plus `X-Content-Type-Options: nosniff`. The summary is inline JSON and contains the requested fields and `formats_available` ordering.

## Frontend

A reusable `ReportDownloadButtons` component renders four explicit compact buttons. It accepts a run ID and uses a URL helper that encodes the ID and format. Real-workspace clicks use an ephemeral anchor with a meaningful `download` name. In demo mode all four controls are disabled with the standard explanation.

The component appears on every report card in `ReportsPage`, in `ReportDetailPage`, and in the action header of terminal `LiveRunDetailWorkspace`. Button clicks stop propagation inside a report card so downloading does not navigate to detail. Pending/running run detail pages do not show export controls.

## Dependencies

Add `jinja2>=3.1.0` and `weasyprint>=60.0` to `requirements.txt` in the backend/reporting dependency group. Pillow already exists and is reused for image optimization.

## Testing and verification

Backend tests build a temporary SQLite/artifact workspace with a failed terminal run, pass/fail/error steps, screenshot, console log, API request, and API response evidence. Tests first fail against the absent exporter and routes, then verify:

- HTML is standalone, escaped, styled, provenance-labelled, and contains a base64 screenshot;
- PDF begins with a valid PDF signature, is parseable, contains expected text/pages, and remains below 10 MB;
- JUnit parses with correct suite/test/failure/error counts and escaped messages;
- SARIF parses with the required schema, rules, results, levels, and app URL;
- summary counts, duration, failure reasons, provenance, and formats are exact;
- missing runs return 404; pending/running runs return the exact 409 detail;
- every download has the required MIME type and attachment filename.

Frontend tests verify four buttons on report cards and terminal run detail, correct encoded URLs and filenames, click isolation, hidden controls for active runs, and disabled demo controls. Final verification runs focused tests, the complete backend suite, smoke journey, complete frontend suite, production build, offline HTML inspection, rendered PDF inspection, XML parsing, SARIF parsing, and Graphify refresh.

## Scope boundaries

This change does not persist new report artifacts, introduce scheduled exports, upload to GitHub/Jenkins/GitLab, add report caching, modify run execution, or remove the legacy JSON report flow.
