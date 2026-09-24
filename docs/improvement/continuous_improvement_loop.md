# Continuous Improvement Loop

QA-AI implements a structured loop:

discover → audit → RCA → fix plan → permission → retest → regression guard → learning

## Orchestration

`ImprovementLoop` coordinates:

1. `SoftwareHealthModel`
2. `FixPlanner`
3. `ChangeImpactAnalyzer`
4. `ImprovementReporter`
5. `RemediationEngine`
6. `RetestOrchestrator`
7. `RegressionGuard`
8. `QualityScoreTracker`
9. `LearningRegistry`

All outputs are persisted as artifacts for downstream reporting and AI reasoning.

## Safety

Remediation is permission-gated and dry-run oriented in default workflow phase handlers.
