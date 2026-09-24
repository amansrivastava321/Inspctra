# Provenance Badges Design

## Goal

Make the source of every backend-backed result, metric, and status visible without changing the data source or overriding backend/demo provenance.

## Component

`ProvenanceBadge` accepts an optional `Provenance` and a human-readable `source` name. It normalizes missing or unknown values to `UNAVAILABLE`, logs a development-only warning for missing values, and renders an inline, non-wrapping badge with a colored dot, short label, and explanatory `title` tooltip.

The six mappings are fixed by the product requirement: real/green, dry-run/yellow, mixed/orange, simulated/blue, demo/purple, and unavailable/gray. Styling follows the existing inline-token UI instead of adding a second CSS framework.

## Placement

- Dashboard: health strip, each summary metric, pass-rate panel, recent-run rows, and data-derived readiness/status widgets.
- Projects/apps, validation packs, live runs, evidence, and reports: every displayed row/card.
- App, pack, run, evidence, and report detail: provenance beside the primary detail heading/status.
- Nested run/evidence rows use their own provenance when available and fall back visibly to `UNAVAILABLE`.

Badges are never placed on buttons, navigation, filters, or offline/empty-state chrome.

## Data Flow and Missing Values

Pages pass the provenance supplied by the selected real or demo workspace directly to the badge. Demo data already carries `DEMO_EXAMPLE`, so no route-based override is introduced. Missing values render `Unavailable`; during development the component warns with the supplied source name.

## Verification

Use component tests for all mappings, tooltips, missing-value fallback, and development warning. Add page-level assertions for demo cards/details and real response surfaces. Run the complete Vitest suite, production build, Playwright demo/offline checks, and read-only backend-online checks.

