# Artifact Contracts

In QA-AI, artifacts are internal APIs. Producers and consumers are decoupled by schema-backed JSON payloads persisted in `ArtifactStore`.

## Contract metadata standard

All validated artifact families are normalized through `ArtifactContract` / `ArtifactMetadata` (`qa_ai.schemas.reporting_schema`) and include:

1. `schema_version`
2. `generated_by`
3. `generated_at`
4. `artifact_type`

`ArtifactContract` also hydrates legacy `metadata` and `_metadata` fields into `artifact_metadata` for backward compatibility.

## ArtifactValidator role

`ArtifactValidator` (`qa_ai.artifacts.artifact_validator`) is the contract boundary:

1. Maps known artifact names to Pydantic models (`MODEL_MAP`).
2. Injects minimum metadata (`artifact_type`, optional `generated_by`) on persistence.
3. Validates/coerces known payloads.
4. Returns safe fallback contract payloads when data is invalid or non-dict.
5. Allows unknown artifact types to pass through unchanged.

This keeps workflow execution resilient even when a producer emits malformed output.

## Major artifact families

1. Audit: findings, RCA, risk, execution context/workflow result.
2. Runtime: execution traces, network traces, replay analysis, runtime monitor/lab artifacts.
3. Evidence: evidence graph and evidence correlation outputs.
4. Improvement: software health, fix plan, remediation plan, retest, regression guard, learning registry, impact analysis.
5. Reporting: summary, dashboard/report visualizations, benchmark summary/metrics.
6. Distributed: actor/session/concurrency/network/offline/sync/chaos/distributed evidence artifacts.
7. Mobile: device registry, emulator/simulator reports, Flutter/Appium/Maestro plans, mobile monitoring/evidence artifacts.
8. AI reasoning: reasoning context, semantic RCA/risk, adaptive plans, evidence synthesis, scenarios, fix reasoning, learning optimization, AI summary.

## Contract discipline

Adding a new artifact contract requires schema definition + validator mapping + producer/consumer tests before it is treated as a stable internal API.
