# Orchestration Model

`WorkflowEngine` is the conductor for QA-AI. It creates execution context, chooses phases, executes each phase handler, persists outputs, and records workflow status.

## WorkflowEngine responsibilities

1. Create and persist `execution_context`.
2. Resolve phase list (`_default_phases` or profile-provided phases).
3. Execute phase handlers through `_execute_phase`.
4. Track `PhaseResult` and `WorkflowResult` status/timing/failures.
5. Persist `workflow_result` and updated context at completion.
6. Gate execution when prerequisites are missing (for example, skip `EXECUTION` if environment is not ready).

## Major workflow phase groups

1. Foundation: `DISCOVERY`, `PLANNING`, `ENVIRONMENT`, optional `EXECUTION`/`EXPLORATION`.
2. Audit: security/API/database/sync/code/dependency/release/performance.
3. Runtime intelligence: evidence, correlation, RCA, runtime validation, scenario/behavior/replay/trace/visual regression.
4. Improvement: health, fix planning, change impact, remediation planning, retest, regression guard, quality tracking, learning.
5. Extended runtime: distributed runtime and mobile runtime phase families.
6. AI reasoning: context, semantic RCA, adaptive planning, evidence synthesis, semantic risk, scenario generation, fix reasoning, learning optimization.
7. Reporting: executive/technical reports, dashboard, visualizations, exports.

## Safe phase extension pattern

When adding a phase:

1. Add enum value in `WorkflowPhase`.
2. Implement a dedicated `_run_<phase>()` method that:
   - transitions context phase
   - reads dependencies from artifacts
   - writes output artifact(s) through `ArtifactStore`
3. Register the phase in `_execute_phase` dispatch with explicit agent name.
4. Wire ordering in `_default_phases` and/or profile configs.
5. Add/update schema contract in `qa_ai/schemas/*` and validator mapping in `ArtifactValidator.MODEL_MAP` for new canonical artifacts.
6. Add tests for handler behavior, contracts, and CLI/profile integration.

## Why artifact-mediated communication

Agents/phases should communicate via artifacts (internal APIs) instead of direct coupling because it:

1. Preserves deterministic boundaries and replayability.
2. Enables independent validation (`ArtifactValidator`) and safe fallback payloads.
3. Supports distributed/mobile/AI/reporting consumers without tight runtime dependencies.
4. Reduces cross-module breakage when workflows evolve.
