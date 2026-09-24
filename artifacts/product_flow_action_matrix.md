# Product Flow Action Matrix
Generated: 2026-05-27

| Label | Page | Expected Behavior | Backend Route | Current Behavior | Fixed | Tested |
|-------|------|-------------------|---------------|------------------|-------|--------|
| Connect app | ProjectsPage | Navigate to /projects/new | — | ✅ Works | ✅ | ✅ |
| Create pack → | CreateValidationPackPage | POST /api/validation-packs, show generate-now prompt | POST /api/validation-packs | ✅ Works | ✅ | ✅ |
| Generate test plan | PackDetailPage / CreateValidationPackPage | POST test-plan/generate, show test cases | POST /api/validation-packs/{id}/test-plan/generate | ✅ Works | ✅ | ✅ |
| Run pack | PackDetailPage | Show review modal → POST /run | POST /api/validation-packs/{id}/run | ✅ Works (dry-run) | ✅ | ✅ |
| Approve permission | LiveRunDetailPage (PermissionModal) | POST /permissions/{id}/approve | POST /api/permissions/{id}/approve | ✅ Works | ✅ | ✅ |
| Deny permission | LiveRunDetailPage (PermissionModal) | POST /permissions/{id}/deny | POST /api/permissions/{id}/deny | ✅ Works | ✅ | ✅ |
| Approve-session permission | LiveRunDetailPage (PermissionModal) | POST /permissions/{id}/approve-session | POST /api/permissions/{id}/approve-session | ✅ Added | ✅ | ✅ |
| Skip permission | LiveRunDetailPage (PermissionModal) | POST /permissions/{id}/skip | POST /api/permissions/{id}/skip | ✅ Added | ✅ | ✅ |
| Cancel run | LiveRunDetailPage | DELETE /runs/{id}, stops background thread | DELETE /api/runs/{id} | ✅ Works | ✅ | ✅ |
| Generate report | LiveRunDetailPage | POST /runs/{id}/report/generate, nav to report | POST /api/runs/{id}/report/generate | ✅ Added | ✅ | ✅ |
| Retest failed | LiveRunDetailPage / ReportDetailPage | POST /runs/{id}/retest-failed, nav to new run | POST /api/runs/{id}/retest-failed | ✅ Added | ✅ | ✅ |
| Export JSON | ReportDetailPage | Download report JSON via controlled anchor | GET /api/reports/{id}/export | ✅ Works | ✅ | — |
| Run retention | MemoryPage | POST /memory/scopes/default/retention | POST /api/memory/scopes/{id}/retention | ⚠️ Button visible but not wired to API call | — | — |
| Semantic recall | MemoryPage | POST /memory/scopes/default/recall | POST /api/memory/scopes/{id}/recall | ✅ Works | ✅ | — |
| Global search (Cmd+K) | Global (App.tsx) | Search apps/packs/runs/reports | — (client-side) | ✅ Added | ✅ | ✅ |
| Run Runtime Doctor | RuntimeDoctorPage | GET /api/runtime-doctor | GET /api/runtime-doctor | ✅ Works | ✅ | ✅ |
| Generate test plan (global) | CreateValidationPackPage after creation | POST test-plan/generate for new pack | POST /api/validation-packs/{id}/test-plan/generate | ✅ Works | ✅ | ✅ |

## Outstanding Non-Critical Gaps

| Gap | Severity | Status |
|-----|----------|--------|
| MemoryPage "Run retention" button not wired | LOW | — |
| RunManager dry-run only (no real app launch) | CAPABILITY_GAP | Intentional, shown honestly |
| Evidence always empty after dry-run | CAPABILITY_GAP | Intentional, shown honestly |
| No Playwright E2E tests | MEDIUM | Scaffold pending |
| AppDetailPage doesn't show runtime requirements / connectors | LOW | Cosmetic improvement |
