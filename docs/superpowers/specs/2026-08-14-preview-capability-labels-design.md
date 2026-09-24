# Preview Capability Labels Design

## Goal

Make Inspectra's execution boundary visible and enforceable in the UI. Working web, API, manual, accessibility, security, performance, and visual-regression capabilities remain enabled. Mobile, desktop, distributed, chaos, CI/CD, and enterprise governance remain visible as future capabilities but cannot be selected or run.

## Design

- Define one frontend capability policy containing display labels, MVP/preview status, tooltips, and legacy action-marker detection.
- Render preview status with a neutral gray `PreviewBadge`, visually separate from provenance and pass/fail status.
- Add an explicit capability selector above the action selector in the validation step editor. MVP choices select a compatible default action; preview choices are disabled and retain the planned-feature tooltip.
- Detect legacy preview steps from their action type, tags, test type, or flow name. Show their Preview badge, prevent edits and enable/disable mutations, and disable both automated and manual pack runs with an explanatory warning.
- Treat non-manual schedules as preview until the scheduler ships. Keep their configured value visible, add a Preview badge, and explain that scheduling is not active.
- Mark Mobile and Desktop app types as Preview in app creation and run target selection. They remain visible but cannot be selected for a new run.
- Reuse the same policy in demo mode; demo routing does not override preview status.

## Existing-surface decisions

- The sidebar has no Mobile, CI/CD, Enterprise, distributed, or chaos routes, so no navigation items are added.
- Settings has no configuration groups for those capabilities and no Test Connection/Execute controls, so no synthetic settings pages or banners are added.
- Existing legacy records remain readable and are never deleted or rewritten.

