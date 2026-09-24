# Adaptive Audit Planning

Adaptive planning converts measured gaps into next-action recommendations.

## Inputs used today

`AdaptiveAuditPlanner` reads:

1. benchmark metrics
2. evidence/risk artifacts
3. reasoning context with Graphify snapshot

## Output behavior

It emits `adaptive_audit_plan` with confidence-scored actions and deterministic references, including recommendations for:

1. coverage improvement
2. runtime verification depth
3. evidence completeness
4. hotspot-oriented validation

## Fallback mode

When no model is available, AI reasoning still runs deterministic/advisory logic and produces artifact outputs. This keeps the pipeline stable in offline or constrained environments.
