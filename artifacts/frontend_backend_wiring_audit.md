# Frontend ↔ Backend Wiring Audit

Generated: 2026-05-26  
Backend port: **8765** (not 8000 — vite proxy bug)  
Audit scope: all 14 pages, all 12 backend routers

---

## Bug Summary (before fixes)

| # | Severity | Location | Bug |
|---|----------|----------|-----|
| 1 | CRITICAL | `vite.config.ts` | Proxy points to port 8000; backend runs on 8765 — all API calls fail in dev |
| 2 | HIGH | `api/client.ts` `checkHealth()` | Calls `GET /api/health` — route does not exist in backend |
| 3 | HIGH | `RuntimeDoctorPage.tsx` | Calls `GET /runtime-doctor/latest` (wrong) and `POST /runtime-doctor/run` (doesn't exist) |
| 4 | HIGH | `RuntimeDoctorPage.tsx` | Response shape mismatch: backend returns `EnvironmentDoctorReport` with `readiness_label`, `missing_items`, `driver_readiness`; frontend expects `readiness_band`, `components`, `things_to_fix`, `summary` |
| 5 | HIGH | `ConnectorsPage.tsx` | Response shape mismatch: backend returns `connector_id`/`ready: bool`/`details`; frontend expects `id`/`status: string`/`detail` |
| 6 | HIGH | `ConnectorsPage.tsx` | Calls `POST /connectors/{id}/test` — route doesn't exist |
| 7 | HIGH | `LiveRunDetailPage.tsx` | Evidence URL wrong: calls `/runs/{id}/evidence`; backend route is `/evidence?run_id={id}` |
| 8 | HIGH | `MemoryPage.tsx` | Stats response unwrap missing: backend returns `{status, stats: {...}}`; frontend reads top-level fields |
| 9 | HIGH | `MemoryPage.tsx` | Patterns response: backend returns dict; frontend expects array |
| 10 | HIGH | `ModelSettingsPage.tsx` | 3 shape mismatches: providers (`provider_id` not `id`, no `status`/`models`), hardware (`total_ram_gb` not `ram_gb`, no `cpu_cores`), profile (different keys) |
| 11 | MEDIUM | `SettingsPage.tsx` | FALLBACK_SETTINGS keys all blocked by backend allowlist (`screenshot_privacy`, `log_redaction`, etc. not in `_ALLOWED_SETTING_KEYS`) |
| 12 | MEDIUM | 8 pages | Old `isMock = data === MOCK_X` pattern — breaks when backend online but returns different ref |
| 13 | MEDIUM | `ValidationPacksPage.tsx` | "Run" button just navigates to `/runs`, never POSTs to backend |
| 14 | LOW | `ReportDetailPage.tsx` | Export PDF button has no onClick handler |

---

## Wiring Matrix

### DashboardPage

| Field | Value |
|-------|-------|
| Route | `/` |
| API calls | `GET /dashboard` |
| Backend route exists | ✅ `GET /api/dashboard` |
| Request payload | N/A (GET) |
| Response type aligned | ⚠️ minor — `capability_gaps`, `runtime_readiness` optional fields; dashboard handles undefined |
| Empty state | ✅ "No apps connected" CTA |
| Offline state | ✅ `OfflineState` component shown |
| Mock state | ✅ Demo mode banner on ApiError(0) |
| Buttons wired | ✅ "Start Live Test" → `/runs/new` |
| Bugs | None critical — works end-to-end once proxy port fixed |

---

### RuntimeDoctorPage

| Field | Value |
|-------|-------|
| Route | `/doctor` |
| API calls | `GET /runtime-doctor/latest` (WRONG), `POST /runtime-doctor/run` (MISSING) |
| Backend route exists | ✅ `GET /api/runtime-doctor` (correct URL is different) |
| Request payload | N/A |
| Response type aligned | ❌ Shape mismatch (see Bug #4) |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ✅ |
| Buttons wired | ❌ "Re-check" calls non-existent POST route |
| Bugs | #3, #4 — URL wrong, shape mismatch, POST route missing |

**Backend `EnvironmentDoctorReport` actual shape:**
```
readiness_score: int
readiness_label: str          ← frontend expects readiness_band
missing_items: List[str]      ← frontend expects things_to_fix: [{id, title, severity, fix}]
recommended_actions: List[str]
driver_readiness: List[DriverReadiness]  ← frontend expects components: [{name, status, version, note}]
playwright_installed: bool
appium_installed: bool
appium_server_running: bool
```

**Fix strategy:** Map `EnvironmentDoctorReport` → `RuntimeDoctorReport` in page; change URL to `/runtime-doctor`; change Re-check to re-call GET (no POST route — refetch is the correct behavior).

---

### ConnectorsPage

| Field | Value |
|-------|-------|
| Route | `/connectors` |
| API calls | `GET /connectors`, `POST /connectors/{id}/test` |
| Backend route exists | ✅ GET; ❌ POST /test doesn't exist |
| Request payload | N/A |
| Response type aligned | ❌ Shape mismatch (see Bug #5) |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old `data === MOCK_CONNECTORS` pattern |
| Buttons wired | ❌ Test button calls non-existent route |
| Bugs | #5, #6, #12 |

**Backend shape:**
```json
{
  "checked_at": "...",
  "connectors": [{"connector_id": "...", "connector_type": "...", "ready": true, "details": "..."}],
  "total": 2,
  "ready": 1
}
```
**Frontend expects:** `Connector[]` with `{id, name, connector_type, status: 'ready'|'not_ready'|'error', detail}`

**Fix strategy:** Map `connector_id→id`, `ready ? 'ready' : 'not_ready'→status`, `details→detail`, use `connector_type` as name. Disable/remove Test button (no backend support).

---

### LiveRunDetailPage

| Field | Value |
|-------|-------|
| Route | `/runs/:runId` |
| API calls | `GET /runs/{id}`, `GET /runs/{id}/evidence` (WRONG) |
| Backend route exists | ✅ GET run; ❌ wrong evidence path |
| Request payload | N/A |
| Response type aligned | ⚠️ Run shape mostly ok |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old pattern |
| Buttons wired | ⚠️ |
| Bugs | #7, #12 |

**Evidence fix:** `GET /runs/{id}/evidence` → `GET /evidence?run_id={id}`

---

### MemoryPage

| Field | Value |
|-------|-------|
| Route | `/memory` |
| API calls | `GET /memory/scopes/default/stats`, `GET /memory/scopes/default/patterns` |
| Backend route exists | ✅ both |
| Request payload | N/A |
| Response type aligned | ❌ stats wrapped, patterns is dict |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old pattern |
| Buttons wired | ✅ (no destructive actions) |
| Bugs | #8, #9, #12 |

**Stats response:** `{status: "ok", stats: {total_memories: N, ...}}` — must unwrap `.stats`  
**Patterns response:** `{pattern_name: count, ...}` dict — must convert to array

---

### ModelSettingsPage

| Field | Value |
|-------|-------|
| Route | `/models` |
| API calls | `GET /models/providers`, `GET /models/profile/current`, `GET /models/hardware` |
| Backend route exists | ✅ all 3 |
| Request payload | N/A |
| Response type aligned | ❌ all 3 shape mismatches (see Bug #10) |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old pattern |
| Buttons wired | ✅ |
| Bugs | #10, #12 |

**Providers:** backend returns `ModelProviderRecord[]` with `provider_id` (not `id`), no `status`, no `models[]`  
**Hardware:** backend returns `total_ram_gb` (not `ram_gb`), `gpu_label` (not `gpu`), no `cpu_cores`  
**Profile:** backend returns `build_profile_report()` dict with different key names

---

### SettingsPage

| Field | Value |
|-------|-------|
| Route | `/settings` |
| API calls | `GET /settings`, `PATCH /settings` |
| Backend route exists | ✅ both |
| Request payload | Keys must be in allowlist |
| Response type aligned | ❌ FALLBACK_SETTINGS keys all blocked (Bug #11) |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old pattern |
| Buttons wired | ✅ |
| Bugs | #11, #12 |

**Allowed keys:** `artifacts_dir`, `default_timeout_seconds`, `run_concurrency_limit`, `log_level`, `dashboard_title`, `enable_runtime_doctor`, `auto_index_artifacts`, `theme`

---

### EvidenceCenterPage

| Field | Value |
|-------|-------|
| Route | `/evidence` |
| API calls | `GET /evidence` |
| Backend route exists | ✅ |
| Request payload | N/A |
| Response type aligned | ✅ |
| Empty state | ✅ |
| Offline state | ❌ — doesn't use `isOffline` from hook |
| Mock state | ❌ old pattern |
| Buttons wired | ✅ |
| Bugs | #12 |

---

### ReportsPage

| Field | Value |
|-------|-------|
| Route | `/reports` |
| API calls | `GET /reports` |
| Backend route exists | ✅ |
| Request payload | N/A |
| Response type aligned | ✅ |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old pattern |
| Buttons wired | ✅ |
| Bugs | #12 |

---

### ReportDetailPage

| Field | Value |
|-------|-------|
| Route | `/reports/:reportId` |
| API calls | `GET /reports/{id}` |
| Backend route exists | ✅ |
| Request payload | N/A |
| Response type aligned | ✅ |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old pattern |
| Buttons wired | ❌ Export PDF button has no onClick |
| Bugs | #12, #14 |

---

### ValidationPacksPage

| Field | Value |
|-------|-------|
| Route | `/validation-packs` |
| API calls | `GET /validation-packs` |
| Backend route exists | ✅ |
| Request payload | N/A |
| Response type aligned | ✅ |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ❌ old pattern |
| Buttons wired | ❌ "Run" just navigates (Bug #13) |
| Bugs | #12, #13 |

---

### AddAppPage

| Field | Value |
|-------|-------|
| Route | `/apps/new` |
| API calls | `GET /projects`, `POST /projects`, `POST /apps` |
| Backend route exists | ✅ all |
| Request payload | ✅ correct |
| Response type aligned | ✅ |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ✅ (no mock path) |
| Buttons wired | ✅ |
| Bugs | None — fully wired |

---

### ProjectsPage

| Field | Value |
|-------|-------|
| Route | `/projects` |
| API calls | `GET /projects`, `POST /projects`, `DELETE /projects/{id}` |
| Backend route exists | ✅ |
| Request payload | ✅ |
| Response type aligned | ✅ |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ✅ |
| Buttons wired | ✅ |
| Bugs | None |

---

### RunsPage / NewRunPage

| Field | Value |
|-------|-------|
| Route | `/runs`, `/runs/new` |
| API calls | `GET /runs`, `POST /runs` |
| Backend route exists | ✅ |
| Request payload | ✅ |
| Response type aligned | ✅ |
| Empty state | ✅ |
| Offline state | ✅ |
| Mock state | ✅ |
| Buttons wired | ✅ |
| Bugs | None critical |

---

## Fix Order

1. `vite.config.ts` — port 8000 → 8765 (blocks everything)
2. `api/client.ts` — add `/health` backend route OR fix healthcheck to use existing route
3. `RuntimeDoctorPage.tsx` — URL fix + shape adapter
4. `ConnectorsPage.tsx` — shape adapter + disable Test button
5. `LiveRunDetailPage.tsx` — evidence URL fix
6. `MemoryPage.tsx` — unwrap stats + convert patterns
7. `ModelSettingsPage.tsx` — 3 shape adapters
8. `SettingsPage.tsx` — align FALLBACK_SETTINGS to allowlist
9. All pages — replace old `isMock = data === MOCK_X` with `isMock` from `useApi`
10. `ValidationPacksPage.tsx` — wire Run button to POST
11. `ReportDetailPage.tsx` — Export PDF stub
12. Backend — add `GET /api/health` route
