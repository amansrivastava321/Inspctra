# Inspectra Backend Provenance System

## Goal

Every backend artifact and status response identifies how its data was produced using a stable, persisted UPPER_SNAKE_CASE provenance value.

## Contract

`Provenance` contains `REAL_EXECUTION`, `DRY_RUN`, `MIXED`, `SIMULATED`, `DEMO_EXAMPLE`, and `UNAVAILABLE`. Pydantic models default to `UNAVAILABLE`; creation and execution paths must set a more precise value when known.

Projects, app targets, validation packs, runs, evidence, and reports persist provenance in SQLite. Existing databases receive additive `ALTER TABLE ... ADD COLUMN provenance` migrations. Legacy runs with evidence are classified as `REAL_EXECUTION`; other missing legacy values remain `UNAVAILABLE`.

Each run step result carries provenance. Run-level provenance is recomputed from completed step results: identical values remain unchanged, differing values become `MIXED`, and all-unavailable remains `UNAVAILABLE`. Reports inherit their run's provenance and evidence inherits its producing step's provenance.

Live backend health and database-backed workspace dashboard responses use `REAL_EXECUTION`. Model-health success uses `REAL_EXECUTION`; failure uses `UNAVAILABLE`.

## Compatibility

The change is additive. Existing fields and route names remain unchanged. Unknown or absent provenance is normalized to `UNAVAILABLE`, and enum values serialize as strings.

## Verification

Tests cover enum serialization, migration and legacy fallback, per-step labeling, run aggregation, entity/list/detail responses, health responses, report inheritance, and the full smoke journey.
