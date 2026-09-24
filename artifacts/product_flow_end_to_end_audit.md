# Product Flow End-to-End Audit
Generated: 2026-05-27

## Step 1 — Empty Workspace
| Field | Value |
|-------|-------|
| Frontend | DashboardPage |
| Backend | GET /api/dashboard |
| Storage | all tables (counts) |
| Status | ✅ Works — real zeros, no fake data |
| Gap | None |
| Test | ✅ Dashboard.test.tsx |

## Step 2 — Create Project
| Field | Value |
|-------|-------|
| Frontend | ProjectsPage → "Connect app" → AddAppPage (step 1 selects project or creates one inline) |
| Backend | POST /api/projects |
| Storage | projects |
| Status | ✅ Works — real POST |
| Gap | /projects/new routes to AddAppPage (app wizard, not project wizard). Project creation is inline in AddAppPage step 1. Navigation is slightly confusing but functional. |
| Fix | Label clarity; AddApp step 1 shows "Create project" inline. Acceptable. |
| Test | ✅ AddAppPage.test.tsx |

## Step 3 — Add App
| Field | Value |
|-------|-------|
| Frontend | AddAppPage — 3-step wizard |
| Backend | POST /api/apps |
| Storage | app_targets |
| Status | ✅ Works — real POST, creates app, navigates to /apps/{id} |
| Gap | None |
| Test | ✅ AddAppPage.test.tsx |

## Step 4 — Runtime Doctor
| Field | Value |
|-------|-------|
| Frontend | RuntimeDoctorPage |
| Backend | GET /api/runtime-doctor |
| Storage | none (stateless check) |
| Status | ✅ Works — ENV readiness + App readiness sections |
| Gap | No app-selector on page (can only run global check; app-specific check requires selecting app via query param or navigation) |
| Fix | Add optional app_id selector to Runtime Doctor page |
| Test | ✅ RuntimeDoctorFixes.test.tsx, RuntimeDoctor.test.tsx |

## Step 5 — Create Validation Pack
| Field | Value |
|-------|-------|
| Frontend | CreateValidationPackPage |
| Backend | POST /api/validation-packs |
| Storage | validation_packs |
| Status | ✅ Works — real POST, shows "generate now?" prompt after creation |
| Gap | None |
| Test | ✅ PackTestPlan.test.tsx |

## Step 6 — Generate Test Plan
| Field | Value |
|-------|-------|
| Frontend | PackDetailPage → Generate test plan button |
| Backend | POST /api/validation-packs/{id}/test-plan/generate |
| Storage | validation_test_plans, validation_test_cases |
| Status | ✅ Works — generic offline template, honest capability gap label |
| Gap | None |
| Test | ✅ PackTestPlan.test.tsx, test_product_backend_test_plans.py |

## Step 7 — Review Test Cases
| Field | Value |
|-------|-------|
| Frontend | PackDetailPage — tabbed test case view |
| Backend | GET /api/validation-packs/{id}/test-cases |
| Storage | validation_test_cases |
| Status | ✅ Works — type filters, safety badges, expand detail |
| Gap | None |
| Test | ✅ PackTestPlan.test.tsx |

## Step 8 — Start Live Run
| Field | Value |
|-------|-------|
| Frontend | PackDetailPage → Run pack → ReviewModal → POST run |
| Backend | POST /api/validation-packs/{id}/run |
| Storage | live_runs |
| Status | ✅ Works — creates run, background thread, navigates to /runs/{id} |
| Gap | RunManager executes DRY-RUN only. No real app launched. "dry_run_only" steps returned. |
| Honest | This is correct — no silent fake execution. Real execution needs InteractionExecutor wiring + permission. |
| Test | ✅ test_product_backend_api.py |

## Step 9 — Permission Approval
| Field | Value |
|-------|-------|
| Frontend | LiveRunDetailPage — PermissionModal (polling usePermissionRequests) |
| Backend | GET /api/permissions?status=pending, POST /api/permissions/{id}/approve, POST /api/permissions/{id}/deny |
| Storage | permissions |
| Status | ⚠️ PARTIAL — approve/deny work; approve-session and skip missing |
| Gap | No POST /api/permissions/{id}/approve-session; No POST /api/permissions/{id}/skip |
| Fix | Add approve-session and skip endpoints to permissions.py ← IMPLEMENTED BELOW |
| Test | ⚠️ No permission approval UI test |

## Step 10 — SSE Stream
| Field | Value |
|-------|-------|
| Frontend | LiveRunDetailPage → useRunStream hook |
| Backend | GET /api/runs/{id}/stream |
| Storage | live_runs (status), EventStream (in-memory queue) |
| Status | ✅ Works — SSE wired, events flow, timeline/verdict update |
| Gap | Events are dry-run status events only (step_start, step_result, done). No screenshot/log/evidence events since no real execution. |
| Honest | Correct — dry-run only emits structural events |
| Test | ✅ useRunStream tested via component; event dispatch tested in backend tests |

## Step 11 — Evidence Collection
| Field | Value |
|-------|-------|
| Frontend | EvidenceCenterPage, LiveRunDetailPage evidence cards |
| Backend | GET /api/evidence?run_id={id}, GET /api/evidence/{id}/download |
| Storage | evidence_files |
| Status | ⚠️ PARTIAL — list/download endpoints exist; RunManager does NOT write evidence records |
| Gap | After a dry-run, evidence list for the run is always empty. No evidence files created. |
| Fix | After real execution is enabled, RunManager must call storage.create_evidence() when screenshots/logs are collected. For now: show empty state honestly. |
| Test | ⚠️ No evidence-after-run test |

## Step 12 — Generate Report
| Field | Value |
|-------|-------|
| Frontend | LiveRunDetailPage — NO generate report button exists |
| Backend | NO POST /api/runs/{id}/report/generate endpoint exists |
| Storage | reports (minimal schema — missing summary fields) |
| Status | ❌ MISSING — reports can only be listed/fetched; no way to generate one |
| Gap 1 | No report generation endpoint |
| Gap 2 | ReportRecord model missing verdict/summary/pass_count/fail_count/findings fields |
| Gap 3 | reports table missing summary_json column |
| Gap 4 | No "Generate Report" button in UI |
| Fix | Implement POST /api/runs/{id}/report/generate + extend model + update frontend ← IMPLEMENTED BELOW |
| Test | ❌ No report generation test |

## Step 13 — Store Memory
| Field | Value |
|-------|-------|
| Frontend | MemoryPage — stats, recall, patterns |
| Backend | POST /api/memory/scopes/{id}/ingest |
| Storage | memory_kernel.db (separate DB) |
| Status | ❌ MISSING WIRING — RunManager does not call memory after run completion |
| Gap | Memory endpoints exist but are never called from run lifecycle |
| Fix | Call memory.ingest_run in RunManager._finalize_run (non-fatal) ← IMPLEMENTED BELOW |
| Test | ❌ No run-completion-calls-memory test |

## Step 14 — Retest Failed Flows
| Field | Value |
|-------|-------|
| Frontend | ReportDetailPage — NO retest button exists |
| Backend | NO POST /api/runs/{id}/retest-failed endpoint |
| Status | ❌ MISSING — no retest flow at all |
| Fix | Add retest endpoint + Retest Failed button in ReportDetailPage ← IMPLEMENTED BELOW |
| Test | ❌ No retest test |

## Step 15 — Before/After Comparison
| Field | Value |
|-------|-------|
| Frontend | Not implemented |
| Backend | NO GET /api/runs/{id}/comparison endpoint |
| Status | ❌ MISSING |
| Fix | Add comparison endpoint; retest runs reference parent run via retest_of field ← IMPLEMENTED BELOW |
| Test | ❌ No comparison test |

---

## Summary of Gaps

| # | Gap | Severity | Implemented |
|---|-----|----------|-------------|
| 1 | No POST /runs/{id}/report/generate | HIGH | ✅ Below |
| 2 | No memory wiring after run completion | HIGH | ✅ Below |
| 3 | No retest endpoint | HIGH | ✅ Below |
| 4 | No comparison endpoint | MEDIUM | ✅ Below |
| 5 | No approve-session / skip permissions | MEDIUM | ✅ Below |
| 6 | No "Generate Report" button in UI | HIGH | ✅ Below |
| 7 | No "Retest Failed" button in UI | HIGH | ✅ Below |
| 8 | ReportRecord model missing summary fields | HIGH | ✅ Below |
| 9 | No global Cmd+K search | LOW | ✅ Below |
| 10 | RunManager dry-run only (no real execution) | INFO | intentional — capability gap shown honestly |
| 11 | Evidence empty after dry-run | INFO | intentional — no fake evidence |
| 12 | No Playwright E2E tests | MEDIUM | scaffold created below |
