# Actionable Dashboard Design

**Date:** 2026-08-14

## Goal

Redesign Inspectra's dashboard around three questions: **What broke?**, **Why?**, and **What should I do next?** Every displayed fact must come from persisted backend data or the isolated demo workspace, carry provenance, and degrade honestly when data or the backend is unavailable.

## Architecture

Extend the existing `GET /api/dashboard` endpoint into a single read-only aggregate. The backend computes one consistent seven-day snapshot from projects, app targets, validation packs, live runs, step results, and evidence. The frontend renders that response without recomputing business metrics or inventing missing values.

The dashboard remains request-time aggregation for the MVP. A persisted snapshot or cache is unnecessary at current SQLite scale and would introduce invalidation concerns. Storage helpers may perform bounded queries, but no new dashboard table or migration is required.

## Time window and run classification

The seven-day window includes today and the six preceding local-calendar UTC days. A run's activity time is selected using this fallback chain:

1. `completed_at`
2. `started_at`
3. `created_at`

Malformed or missing timestamps are excluded from seven-day metrics but may still contribute to lifetime counts. Daily buckets are returned oldest-to-newest with an ISO date, passed count, failed count, total count, and nullable pass rate. All seven days are present. A day with no runs has zero counts and a null pass rate, so the UI can label it “No runs” rather than interpreting it as 0%.

A run is failed when its status is `failed`, its explicit verdict is `fail` or `failed`, or any step result is failed. A run is passed when it is terminal and its result contains no failure. Pending, running, cancelled, blocked, skipped, dry-run-only, or otherwise indeterminate runs do not affect pass-rate calculations.

## Failure normalization

The latest failure card keeps the exact raw failure text. The breakdown groups recent failures into stable categories. HTTP status metadata takes precedence over message matching:

- **HTTP 4xx:** explicit status 400–499; otherwise “client error,” “bad request,” “unauthorized,” or “not found.”
- **HTTP 5xx:** explicit status 500–599; otherwise “server error” or “internal error.”
- **Timeout:** “timeout,” “timed out,” or “exceeded time limit.”
- **Element not found:** “element not found,” “selector not found,” “no element matches,” or “could not find.”
- **Assertion failed:** “assertion,” “expected,” “but was,” “does not contain,” or “does not match.”
- **Network error:** “connection refused,” “dns,” “network,” “unreachable,” or “econnrefused.”
- **Browser crash:** “browser,” “chromium,” “playwright,” or “launch failed.”
- **Unknown:** everything else.

After HTTP precedence, more specific textual rules are evaluated before broad ones. Each failed run contributes once to the category of its most relevant failed step or run-level error. The top three categories are sorted by descending count and then stable category order. Each item includes its category label, count, and contributing run IDs.

## Dashboard response

`DashboardSummary` keeps existing fields for additive compatibility and adds:

- `recent_failed_run`: a compact run reference with run, pack, and app identity; exact failure reason; activity timestamp; provenance; and optional screenshot evidence ID.
- `failure_reasons`: normalized category, count, and run IDs.
- `pass_rate_7d`: seven explicit daily buckets.
- `total_runs_7d` and `passed_runs_7d`.
- `projects_count`, `apps_count`, and `packs_count`, while retaining the existing singular count names during migration.
- `coverage`: apps with at least one pack, total apps, percentage, and optional most recent pack timestamp.
- `last_run_at` and `last_run_provenance`.
- top-level aggregate `provenance`.

The aggregate provenance is the unique provenance when all contributing records agree, `MIXED` when multiple sources contribute, and `UNAVAILABLE` when no trustworthy source exists. Referenced runs and screenshots retain their own provenance. Persisted database counts are `REAL_EXECUTION`; demo data remains `DEMO_EXAMPLE` through the isolated demo workspace.

## Evidence selection

For the most recent failed run, select the newest persisted evidence whose type or MIME type identifies it as an image or screenshot. Return only its evidence ID and metadata; the frontend uses the existing path-safe `/api/evidence/{id}/download` endpoint.

`DashboardScreenshot` shows a clickable thumbnail and accessible lightbox when the artifact loads. If an API-only failure has no screenshot, the thumbnail region shows a restrained “No screenshot captured” placeholder. A missing or unreadable linked artifact transitions to “Screenshot unavailable” rather than displaying a broken image. HTML evidence is never injected.

## Frontend states

`DashboardPage` delegates presentation to focused components under `components/dashboard/`:

- `DashboardHero` renders exactly one state: latest failure, all clear, no runs, or backend offline.
- `DashboardScreenshot` renders the optional evidence image and lightbox fallback.
- `FailureContext` renders normalized reasons and seven CSS bars without adding a chart dependency.
- `CoverageOverview` renders project, app, pack, covered-app, and last-pack facts.
- `DashboardActions` renders state-specific task CTAs.

The failure hero dominates the top of the content area and includes the app/pack name, exact reason, exact and relative timestamps, Failed status, provenance, run detail link, and run-filtered Evidence Center link. The all-clear hero reports the actual latest passed run and seven-day pass count. The empty hero sends users to pack creation or the demo workspace. The offline hero contains Retry and Try Demo only, with no metrics.

When failures exist, the secondary section shows the top reasons and seven-day pass bars. Otherwise it shows coverage. The action section follows the requested state mapping. “Re-run failed pack” starts the entire latest failed pack with its stored app target and navigates to the new run. It is disabled while submitting and reports an inline actionable error on failure.

Scheduling remains non-executable and carries the existing Preview treatment. Demo write actions, including rerun and pack creation, remain disabled with the standard real-workspace tooltip. “Try Demo” remains available from empty and offline real-workspace states.

## Navigation and filters

- View Details: `/runs/{run_id}`
- Investigate Evidence / Review Evidence: `/evidence?run_id={run_id}` when a run is known
- View runs for a failure category: `/runs?failure_category={category}`. This phase navigates with the filter query and preserves the contributing IDs in the dashboard response; implementing richer runs-page filtering remains later scope.
- Create Pack: `/packs/new`
- Connect App: `/projects/new`
- Try Demo: `/demo`

Existing routes remain unchanged.

## Error handling and honesty

- Backend unreachable: show the dedicated offline hero and no summary content.
- Backend error with no data: show the existing error state with Retry.
- Missing aggregate fields from a legacy response: treat the values as unavailable, never synthesize counts.
- Missing provenance: render `UNAVAILABLE` and retain the existing development warning behavior.
- Rerun failure: leave the dashboard intact and show a concise inline error.
- Screenshot 404 or decode error: show the unavailable placeholder while preserving all textual failure evidence.

## Testing

Backend tests cover:

- empty summary and additive response compatibility;
- activity timestamp fallback and seven-day cutoff;
- seven daily buckets including no-run days;
- failed/passed/indeterminate run classification;
- HTTP status precedence and every normalization category;
- stable top-three aggregation and contributing run IDs;
- coverage across apps and packs;
- newest screenshot selection and API-only failure without a screenshot;
- aggregate and artifact provenance.

Frontend tests cover:

- failed hero, exact reason, provenance, screenshot, normalized breakdown, bars, and actions;
- all-clear hero and coverage overview;
- no-run workspace CTAs;
- backend offline and retry;
- demo badges and disabled mutation CTAs;
- rerun success/error behavior;
- screenshot lightbox, missing screenshot, and broken-artifact fallback;
- exact and relative timestamp display.

The focused backend and frontend tests run first, followed by the complete frontend suite, relevant backend suite, production TypeScript/Vite build, and browser screenshots for failure, all-clear, empty, offline, and demo states. Graphify is refreshed after code changes.

## Scope boundaries

This phase does not add scheduling, bulk execution, historical dashboard snapshots, step-level dashboard retry, new chart dependencies, mobile execution, or advanced runs-page filtering. Existing generic readiness and synthetic health widgets are removed from the dashboard rather than repurposed.
